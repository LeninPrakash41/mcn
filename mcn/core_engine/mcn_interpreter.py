"""
MCN Interpreter — public orchestration layer.

All language implementation lives in dedicated modules:
  lexer.py      — tokenisation with column tracking + INDENT/DEDENT
  parser.py     — token stream → typed AST (ast_nodes.py)
  evaluator.py  — tree-walking execution with lexical scoping

This file wires those three modules together and registers all built-in
functions.  The public API is unchanged: MCNInterpreter.execute(code).

Backward-compat exports:
  MCNLexer  = Lexer    (used by test/debug scripts)
  MCNParser = Parser   (used by test/debug scripts)
  TokenType = TT       (alias for token-type enum)
"""
import os
import traceback
import time
from typing import Any, Callable, Dict, Optional, List

from .mcn_logger import log_error, log_step, log_performance
from .lexer     import Lexer, TT, Token
from .parser    import Parser
from .evaluator import Evaluator, MCNError

# ── Backward-compat aliases ────────────────────────────────────────────────────
MCNLexer  = Lexer
MCNParser = Parser
TokenType = TT

# ── Core protection metadata ───────────────────────────────────────────────────
MCN_CORE_VERSION     = "2.0.0"
MCN_CORE_SIGNATURE   = "MCN-OFFICIAL-INTERPRETER"
MCN_TRADEMARK_NOTICE = "MCN is a trademark of MCN Foundation"
MCN_COPYRIGHT        = "Copyright (c) 2025 MCN Foundation"


def verify_mcn_authenticity() -> bool:
    """Verify this is an official MCN distribution."""
    sig = os.path.join(os.path.dirname(__file__), ".mcn_official")
    return os.path.exists(sig)


class ReturnValue(Exception):
    """Kept for any external code that may catch it."""
    def __init__(self, value: Any):
        self.value = value
        super().__init__()


# ── Main interpreter ───────────────────────────────────────────────────────────

class MCNInterpreter:
    """
    High-level MCN interpreter.

    Lifecycle:
      1. Instantiate once (registers built-ins, initialises v2 features).
      2. Call .execute(code) one or more times.
      3. Optionally call .register_function(name, fn) to add external callables.

    The underlying Evaluator maintains a persistent global environment across
    multiple .execute() calls in the same session (REPL mode), which matches
    the previous behaviour.
    """

    def __init__(self):
        # Built-in function registry — shared with the Evaluator so that
        # user-defined functions declared during execution are also visible.
        self._functions: Dict[str, Callable] = {}
        self._register_builtin_functions()
        self._init_v2_features()

        # Create the evaluator with the shared functions dict
        self._evaluator = Evaluator(self._functions)

    # ── Backward-compat properties (used by tests / server) ───────────────────

    @property
    def variables(self) -> Dict[str, Any]:
        """Flat view of the global scope (backward-compat)."""
        return self._evaluator.variables

    @property
    def functions(self) -> Dict[str, Callable]:
        return self._functions

    @property
    def user_functions(self) -> Dict[str, Callable]:
        return self._functions

    # ── Public API ─────────────────────────────────────────────────────────────

    def register_function(self, name: str, func: Callable) -> None:
        """Expose a Python callable to MCN scripts."""
        self._functions[name] = func

    def execute(self, code: str, file_path: str = None,
                quiet: bool = False) -> Any:
        """
        Lex, parse, and evaluate a MCN source string.

        Parameters
        ----------
        code      : MCN source text
        file_path : used in error / log messages only
        quiet     : suppress step-level logging (used in production/server mode)
        """
        import textwrap
        code = textwrap.dedent(code)
        start = time.time()
        try:
            if not quiet:
                log_step("Starting MCN execution", file_path=file_path)

            # ── Lexical analysis ──────────────────────────────────────────────
            tokens = Lexer(code).tokenize()
            if not quiet:
                log_step("Tokenisation complete", token_count=len(tokens))

            # ── Parsing ───────────────────────────────────────────────────────
            program = Parser(tokens).parse()
            if not quiet:
                log_step("Parsing complete", statements=len(program.body))

            # ── Evaluation ────────────────────────────────────────────────────
            result = self._evaluator.execute_program(program)
            elapsed = time.time() - start
            if not quiet:
                log_performance(
                    "MCN execution", elapsed,
                    statements=len(program.body),
                    variables=len(self.variables),
                    functions=len(self._functions),
                )
            return result

        except Exception as exc:
            elapsed = time.time() - start
            msg     = str(exc)

            if "LexError" in msg or "ParseError" in msg:
                error_type = "SYNTAX_ERROR"
            elif "Undefined variable" in msg or "Undefined function" in msg:
                error_type = "REFERENCE_ERROR"
            elif "RuntimeError" in msg:
                error_type = "RUNTIME_ERROR"
            else:
                error_type = "RUNTIME_ERROR"

            log_error(
                error_type, msg,
                context={
                    "code_snippet": code[:200] + ("..." if len(code) > 200 else ""),
                    "execution_time": elapsed,
                    "traceback": traceback.format_exc(),
                },
                file_path=file_path,
            )
            raise Exception(f"MCN {error_type}: {msg}") from exc

    # ── Built-in function registration ─────────────────────────────────────────

    def _register_builtin_functions(self):
        from .mcn_runtime import MCNRuntime
        self.runtime = MCNRuntime()

        # ── Core runtime built-ins ────────────────────────────────────────────
        self._functions.update({
            "log":                self.runtime.log,
            "echo":               self._echo,
            "trigger":            self._trigger_event_or_http,
            "query":              self.runtime.query,
            "workflow":           self.runtime.workflow,
            "env":                self._env,
            "read_file":          self._read_file,
            "write_file":         self._write_file,
            "append_file":        self._append_file,
            "fetch":              self._fetch,
            "send_email":         self.runtime.send_email,
            "hash_data":          self.runtime.hash_data,
            "encode_base64":      self.runtime.encode_base64,
            "decode_base64":      self.runtime.decode_base64,
            "now":                self.runtime.now,
            "format_date":        self.runtime.format_date,
            "connect_postgresql": self.runtime.connect_postgresql,
            "connect_mongodb":    self.runtime.connect_mongodb,
        })

        # ── AI / intelligent primitives (Layer 1) ─────────────────────────────
        from .ai_builtins import register_ai_builtins
        register_ai_builtins(self._functions)

        # ── Standard library (Layer 2): session, cache, memory, vector, RAG,
        #    auth, data, strings, arrays, math, queue, crypto ─────────────────
        from .stdlib_builtins import register_stdlib_builtins
        register_stdlib_builtins(self._functions)

    def _init_v2_features(self):
        """Initialise MCN 2.0 features (packages, async, type hints, AI context)."""
        from .mcn_extensions import (
            MCNAIContext, MCNPackageManager, MCNAsyncRuntime, MCNTypeChecker,
            create_db_package, create_http_package, create_ai_package,
        )

        self.ai_context      = MCNAIContext()
        self.package_manager = MCNPackageManager()
        self.async_runtime   = MCNAsyncRuntime()
        self.type_checker    = MCNTypeChecker()

        self.package_manager.add_package("db",   create_db_package())
        self.package_manager.add_package("http", create_http_package())
        self.package_manager.add_package("ai",   create_ai_package())

        self._functions.update({
            "task": self._create_task,
            "await": self._await_tasks,
            "use":  self._use_package,
            "type": self._set_type_hint,
            
            # v3.0 / ML / IoT / Event Primitives
            "train":               self._train_ml_model,
            "predict":             self._predict_ml_model,
            "load_dataset":        self._load_ml_dataset,
            "preprocess":          self._preprocess_dataset,
            "deploy_model":        self._deploy_ml_model,
            "batch_predict":       self._batch_predict,
            "compare_models":      self._compare_models,
            "export_model":        self._export_ml_model,
            "fine_tune":           self._fine_tune_model,
            "get_training_status": self._get_training_status,
            "generate_postman":    self._generate_postman_collection,
            "device":              self._device_operation,
            "on":                  self._on_event,
            "agent":               self._agent_operation,
            "pipeline":            self._pipeline_operation,
            "translate":           self._translate_natural,
            "ui":                  self._ui_operation,
        })

    # ── Built-in implementations ───────────────────────────────────────────────

    def _echo(self, message: Any) -> None:
        print(message)

    def _trigger_event_or_http(self, target: str, payload: Any = None, *args, **kwargs):
        if isinstance(target, str) and (target.startswith("http://") or target.startswith("https://")):
            return self.runtime.trigger(target, payload, *args, **kwargs)
        else:
            self._ensure_v3_systems()
            data = payload if isinstance(payload, dict) else {}
            return self.event_system.trigger_event(target, data)

    def _env(self, key: str) -> Optional[str]:
        return os.getenv(key)

    def _read_file(self, filepath: str) -> str:
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as exc:
            raise Exception(f"Failed to read file '{filepath}': {exc}") from exc

    def _write_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(str(content))
        except Exception as exc:
            raise Exception(f"Failed to write file '{filepath}': {exc}") from exc

    def _append_file(self, filepath: str, content: str) -> None:
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(str(content))
        except Exception as exc:
            raise Exception(f"Failed to append to '{filepath}': {exc}") from exc

    def _fetch(self, url: str) -> Dict:
        import requests
        try:
            resp = requests.get(url, timeout=30)
            body = (
                resp.json()
                if resp.headers.get("content-type", "").startswith("application/json")
                else resp.text
            )
            return {
                "status_code": resp.status_code,
                "data":        body,
                "success":     200 <= resp.status_code < 300,
            }
        except Exception as exc:
            return {"status_code": 0, "data": str(exc), "success": False}

    def _create_task(self, name: str, func_name: str, *args: Any) -> str:
        if func_name in self._functions:
            task = self.async_runtime.create_task(
                name, self._functions[func_name], *args
            )
            return f"Task '{name}' created"
        raise Exception(f"Function '{func_name}' not found")

    def _await_tasks(self, *task_names: str) -> Any:
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(
                self.async_runtime.await_tasks(*task_names)
            )
        finally:
            loop.close()

    def _ensure_v3_systems(self):
        if not hasattr(self, 'module_system'):
            from .mcn_module_system import MCNModuleSystem
            from .mcn_v3_extensions import (
                MCNModelRegistry, MCNEventSystem, MCNIoTConnector,
                MCNAgentSystem, MCNDataPipeline, MCNNaturalLanguage
            )
            self.model_registry = MCNModelRegistry()
            self.event_system = MCNEventSystem()
            self.iot_connector = MCNIoTConnector()
            self.agent_system = MCNAgentSystem(self.model_registry)
            self.pipeline_system = MCNDataPipeline(self.model_registry)
            self.nl_system = MCNNaturalLanguage(self.model_registry)
            self.module_system = MCNModuleSystem()

    def _use_package(self, package_name: str) -> str:
        from .mcn_packages import get_registry, PackageNotFoundError

        def _bind(pkg_name: str, pkg_fns: dict) -> str:
            """Bind package functions both flat and as a namespaced dict."""
            self._functions.update(pkg_fns)
            # Also expose as package_name.fn() namespace object
            # Use only the last path component: "accenture/healthcare" → "healthcare"
            ns_key = pkg_name.split("/")[-1].replace("-", "_")
            self._evaluator.globals.define(ns_key, pkg_fns)
            return f"Package '{pkg_name}' loaded ({len(pkg_fns)} exports)"

        # 1. Try the new registry (bundled + disk + project)
        try:
            pkg_fns = get_registry().load(package_name)
            return _bind(package_name, pkg_fns)
        except PackageNotFoundError:
            pass

        # 2. Fall back to legacy in-memory package_manager (db/http/ai packages)
        pkg_fns = self.package_manager.get_package_functions(package_name)
        if pkg_fns:
            return _bind(package_name, pkg_fns)

        # 3. Fall back to v3.0 module system (for ai_v3, iot, events, agents, natural, pipeline)
        try:
            self._ensure_v3_systems()
            pkg_fns = self.module_system.use_package(package_name, self)
            if pkg_fns:
                return _bind(package_name, pkg_fns)
        except Exception:
            pass

        raise Exception(
            f"Package '{package_name}' not found.\n"
            f"Built-in packages: stripe, twilio, resend, slack, openai, healthcare, finance\n"
            f"Install custom: mcn install --path ./my_package"
        )

    def _set_type_hint(self, var_name: str, var_type: str) -> str:
        self.type_checker.add_type_hint(var_name, var_type)
        return f"Type hint set: {var_name} -> {var_type}"

    # ── MCN v3.0 Primitives implementations ─────────────────────────────────────

    def _train_ml_model(self, model_type: str, dataset_name: str, target_column: str, **kwargs):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.train_model(model_type, dataset_name, target_column, **kwargs)
        except Exception as e:
            return {"error": f"ML training failed: {str(e)}"}
    
    def _predict_ml_model(self, model_id: str, input_data: dict):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.predict(model_id, input_data)
        except Exception as e:
            return {"error": f"ML prediction failed: {str(e)}"}
    
    def _load_ml_dataset(self, name: str, file_path: str, **kwargs):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.load_dataset(name, file_path, **kwargs)
        except Exception as e:
            return {"error": f"Dataset loading failed: {str(e)}"}
    
    def _preprocess_dataset(self, dataset_name: str, operations: list):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.preprocess_dataset(dataset_name, operations)
        except Exception as e:
            return {"error": f"Dataset preprocessing failed: {str(e)}"}
    
    def _deploy_ml_model(self, model_id: str, endpoint_name: str = None):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.deploy_model(model_id, endpoint_name)
        except Exception as e:
            return {"error": f"Model deployment failed: {str(e)}"}
    
    def _batch_predict(self, model_id: str, data_file: str, output_file: str = None):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.batch_predict(model_id, data_file, output_file)
        except Exception as e:
            return {"error": f"Batch prediction failed: {str(e)}"}
    
    def _compare_models(self, dataset_name: str, target_column: str, models: list = None):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.model_comparison(dataset_name, target_column, models)
        except Exception as e:
            return {"error": f"Model comparison failed: {str(e)}"}
    
    def _export_ml_model(self, model_id: str, format_type: str = "json"):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.export_model(model_id, format_type)
        except Exception as e:
            return {"error": f"Model export failed: {str(e)}"}
    
    def _fine_tune_model(self, base_model: str, training_data: str, new_model_name: str, **kwargs):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.fine_tune_model(base_model, training_data, new_model_name, **kwargs)
        except Exception as e:
            return {"error": f"Fine-tuning failed: {str(e)}"}
    
    def _get_training_status(self, job_id: str):
        try:
            from .mcn_ml_system import get_ml_system
            ml_system = get_ml_system()
            return ml_system.get_training_status(job_id)
        except Exception as e:
            return {"error": f"Status check failed: {str(e)}"}
    
    def _generate_postman_collection(self, output_dir: str = "postman_exports"):
        try:
            from .mcn_postman_generator import generate_postman_collection
            result = generate_postman_collection(output_dir)
            return {
                "success": True,
                "collection_file": result["collection_file"],
                "environment_file": result["environment_file"],
                "endpoints_count": result["endpoints_count"],
                "message": f"Postman collection generated with {result['endpoints_count']} endpoints"
            }
        except Exception as e:
            return {"error": f"Postman generation failed: {str(e)}"}
            
    def _device_operation(self, operation: str, device_id: str = None, config: dict = None):
        try:
            self._ensure_v3_systems()
            if operation == "register":
                device_type = config.get("type", "unknown") if isinstance(config, dict) else "unknown"
                result = self.iot_connector.register_device(device_id, device_type, config or {})
                return {"success": True, "message": result}
            elif operation == "read":
                val = self.iot_connector.read_device(device_id)
                return {"value": val}
            elif operation == "command":
                cmd = config.get("command", "unknown") if isinstance(config, dict) else "unknown"
                result = self.iot_connector.send_command(device_id, cmd, config or {})
                return {"success": True, "message": result}
            return {"error": f"Unknown device operation: {operation}"}
        except Exception as e:
            return {"error": str(e)}

    def _on_event(self, event_name: str, handler_func: Any = None):
        try:
            self._ensure_v3_systems()
            self.event_system.on_event(event_name, handler_func)
            return f"Registered event handler for {event_name}"
        except Exception as e:
            return {"error": str(e)}

    def _agent_operation(self, operation: str, name: str = None, options: dict = None, **kwargs):
        try:
            self._ensure_v3_systems()
            opts = {}
            if isinstance(options, dict):
                opts.update(options)
            opts.update(kwargs)
            
            if operation == "create":
                prompt = opts.get("prompt", "")
                model = opts.get("model")
                tools = opts.get("tools")
                return self.agent_system.create_agent(name, prompt, model, tools)
            elif operation == "activate":
                return self.agent_system.activate_agent(name)
            elif operation == "think":
                self.agent_system.activate_agent(name)
                input_data = opts.get("input", "")
                return self.agent_system.agent_think(name, input_data)
            return f"Agent {operation} on {name} simulated"
        except Exception as e:
            return {"error": str(e)}

    def _pipeline_operation(self, operation: str, name: str = None, steps_or_data=None):
        try:
            self._ensure_v3_systems()
            if operation == "create":
                step_list = []
                if isinstance(steps_or_data, list):
                    for step in steps_or_data:
                        if isinstance(step, str):
                            step_list.append({"type": step, "params": {}})
                        elif isinstance(step, dict):
                            step_list.append(step)
                return self.pipeline_system.create_pipeline(name, step_list)
            elif operation == "run":
                return self.pipeline_system.run_pipeline(name, steps_or_data)
            return f"Pipeline {operation} simulated"
        except Exception as e:
            return {"error": str(e)}

    def _translate_natural(self, natural_text: str, execute: bool = False):
        try:
            self._ensure_v3_systems()
            if execute:
                translated = self.nl_system.translate(natural_text)
                return self.execute(translated)
            return self.nl_system.translate(natural_text)
        except Exception as e:
            return {"error": str(e)}

    def _ui_operation(self, operation: str, text_or_format=None):
        try:
            from .mcn_runtime import MCNRuntime
            runtime = MCNRuntime()
            if hasattr(runtime, "ui_operation"):
                return runtime.ui_operation(operation, text_or_format)
            return f"UI operation {operation} simulated"
        except Exception as e:
            return {"error": str(e)}
