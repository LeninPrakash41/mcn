# Legacy examples

These scripts don't run on current MCN. They are kept for reference while
they are rewritten; see the examples one level up for working MCN.

| Script | Why it doesn't run |
|---|---|
| business_automation_complete, dynamic_systems_integration, ecommerce_platform, frontend-integration-demo, real_business_demo | Older brace-based syntax (`function f() { ... }`, `if x { ... }`) that the parser no longer supports |
| ai_v3_demo, complete_v3_test, developer_tools_demo, dynamic_systems_demo, v2_features_demo, v3_complete_demo, v3_enhanced_demo | A planned API that was never built (`register`, `set_model`, `run`, `search`, `install`, `get`, `analyze_sentiment`, and the `swagger`, `codegen` and `monitoring` packages). The same features are shown by `v3_ai_models.mcn`, `v3_iot_automation.mcn`, `async_tasks.mcn` and `ai_primitives_test.mcn` |
