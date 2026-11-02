# MCN Language Specification (v3.0)

**License:** MIT  
**Status:** Standardized Open-Source Specification  
**Maintainer:** MCN Open Source Community

---

## 1. Overview & Design Philosophy

The **Macincode Network (MCN)** Language is a declarative, high-density Domain-Specific Language (DSL) designed for full-stack, multi-platform software architecture. 

### Core Tenets
1. **Single Source of Truth (SSOT)**: A single `.mcn` file defines relational data models, backend REST/CRUD services, security guards, React web interfaces, and Flutter mobile views.
2. **Ejectable Compilers**: The MCN compiler transpiles directly into standard, idiomatic code (React 18, Flutter, PostgreSQL DDL, Electron) with **zero proprietary runtime lock-in**.
3. **Deterministic & Guarded**: Declarative `@guard` decorators enforce cryptographic JWT authentication and role-based access control (RBAC) at compile-time and runtime.
4. **Multimodal AI Synergy**: Designed with clean, human-readable grammar optimized for LLM generation, validation, and automated reasoning from design mockups and requirement documents.

---

## 2. Lexical Grammar & Keywords

### 2.1 Keywords
```
contract    service     component    guard       endpoint
get         post        put          delete      patch
analytics   pipeline    stage        model       var
if          else        while        for         in
return      true        false        null
```

### 2.2 Data Types
* **Primitive Types**: `string`, `int`, `float`, `boolean`, `datetime`, `uuid`
* **Collection Types**: `list<T>`, `map<string, T>`
* **Relational Schema Directives**: `primary_key`, `autoincrement`, `unique`, `not_null`, `default(...)`

---

## 3. Structural Primitives

### 3.1 Data Contracts (`contract`)
Defines database tables and JSON serialization schemas:
```mcn
contract User {
    id: int primary_key autoincrement
    email: string unique not_null
    name: string not_null
    role: string default("viewer")
    created_at: datetime default(now())
}
```

### 3.2 Services & Endpoints (`service`)
Defines REST API endpoints with declarative security:
```mcn
service UserService {
    @guard(role="admin")
    get /api/v1/users -> list<User> {
        return query("SELECT * FROM User ORDER BY created_at DESC")
    }

    @guard(role="admin")
    post /api/v1/users(data: User) -> User {
        return insert("User", data)
    }
}
```

### 3.3 UI Components (`component`)
Defines reactive user interface structures that transpile to React and Flutter:
```mcn
component UserDirectory {
    state users: list<User> = []
    
    on_mount {
        users = fetch("/api/v1/users")
    }

    render {
        <Card title="User Management">
            <DataTable 
                data={users} 
                columns={["id", "name", "email", "role"]} 
            />
        </Card>
    }
}
```

### 3.4 BI & Analytics Matrix (`analytics`)
Defines multidimensional pivot matrices and KPI aggregations:
```mcn
analytics RevenueMatrix {
    source: "SELECT * FROM Deals WHERE status = 'won'"
    dimensions: [region, category]
    metrics: [sum(amount), count(id), avg(amount)]
}
```

### 3.5 AI Workflow Pipelines (`pipeline`)
Defines multi-stage LLM chaining and data synthesis:
```mcn
pipeline DocumentExtractionPipeline {
    stage 1: ingest(pdf_document)
    stage 2: llm_transform(model="gemini-1.5-pro", prompt=PromptTemplate)
    stage 3: schema_guard(target=UserContract)
}
```

---

## 4. Compiler Targets & Code Generation

| Target | Output Artifact | Generated Framework |
|---|---|---|
| **Web Frontend** | `frontend/src/` | React 18, Vite, Tailwind CSS, shadcn/ui |
| **Mobile App** | `mobile/lib/` | Flutter 3.x, `mcn_ui` Material 3 Package |
| **Desktop Shell** | `desktop/` | Electron, TypeScript, Vite |
| **Database Migrations** | `migrations/*.sql` | PostgreSQL / Supabase DDL with RLS Policies |
| **API Documentation** | `openapi.json` | OpenAPI 3.0.3 Specification & Swagger UI |
| **Production Container** | `Dockerfile` | Multi-stage Node 20 + Python 3.12 Non-root |

---

## 5. Open Source Tooling Ecosystem

1. **Official VS Code Extension (`mcn-vscode-extension`)**:
   * TextMate Syntax Grammar (`syntaxes/mcn.tmLanguage.json`)
   * Language Configuration (`language-configuration.json`)
   * Snippet Library (`snippets/mcn.code-snippets`)
2. **Interactive Swagger Explorer (`/docs`)**:
   * Live endpoint testing with Bearer JWT tokens.
3. **Web Playground Studio (`mcn/web-playground`)**:
   * Browser-based IDE with live dual Web + Flutter phone simulator previews.
