# Proyecto 3: Pipeline Dashboard — Guía SDD con Claude Code

## 🎯 Objetivo de aprendizaje

Aprender a escribir **especificaciones para sistemas multi-componente**:
- Specs separadas para backend, frontend, y comunicación entre ambos
- Contratos compartidos (los schemas que ambos lados deben respetar)
- Especificar comportamiento en tiempo real (WebSockets)
- Descomponer un sistema complejo en fases implementables

```
Spec de datos compartidos → Spec backend → Spec frontend → Spec WebSocket → Integración
```

---

## 🔄 Qué cambió respecto al Proyecto 2

| Proyecto 2 (API) | Proyecto 3 (Full-stack) |
|-------------------|-------------------------|
| 1 spec de datos + 1 spec de endpoints | 4 specs que se referencian entre sí |
| Solo backend | Backend + Frontend + WebSocket |
| Cliente = curl / tests | Cliente = UI en React |
| Datos estáticos | Datos en tiempo real (pipelines que progresan) |
| 1 sesión de Claude Code | Múltiples sesiones (backend y frontend separados) |

---

## 📁 Los archivos de spec (léelos EN ESTE ORDEN)

1. **CLAUDE.md** → Reglas globales del proyecto
2. **specs/shared-contracts.spec.md** → Los modelos de datos que backend Y frontend comparten (LEER PRIMERO)
3. **specs/backend-api.spec.md** → Endpoints REST + WebSocket del backend
4. **specs/frontend-ui.spec.md** → Componentes React y su comportamiento
5. **PROMPTS-CLAUDE-CODE.md** → Prompts exactos para cada fase

---

## 🏗️ Arquitectura del sistema

```
┌─────────────────────────────────────────────┐
│                  Frontend                    │
│               (React + Vite)                 │
│                                              │
│  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │
│  │ Pipeline  │ │ Pipeline │ │   Stage      │ │
│  │ List      │ │ Detail   │ │   Progress   │ │
│  └──────────┘ └──────────┘ └──────────────┘ │
│         │            │             │         │
│         └────────────┼─────────────┘         │
│                      │                       │
│              WebSocket + REST                │
└──────────────────────┼───────────────────────┘
                       │
┌──────────────────────┼───────────────────────┐
│                      │        Backend        │
│               (FastAPI + SQLite)             │
│                                              │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ │
│  │ REST API │ │ WebSocket    │ │ Pipeline  │ │
│  │ /api/*   │ │ /ws/pipeline │ │ Simulator │ │
│  └──────────┘ └──────────────┘ └──────────┘ │
└──────────────────────────────────────────────┘
```

---

## 🏁 Fases del proyecto

| Fase | Qué implementas | Qué aprendes de SDD |
|------|-----------------|---------------------|
| 1 | Modelos + DB + simulador de pipelines | Specs con estados y transiciones |
| 2 | API REST (CRUD + trigger + logs) | Specs que reusan contratos compartidos |
| 3 | WebSocket para updates en tiempo real | Especificar protocolos de comunicación |
| 4 | Frontend: lista de pipelines + detalle | Specs de UI basadas en contratos de datos |
| 5 | Frontend: tiempo real + dashboard | Specs de comportamiento reactivo |
| 6 | Tests E2E + integración completa | Specs de integración entre componentes |

---

## 💡 La lección clave de este proyecto

**Los contratos compartidos son el pegamento del sistema.**

Si el backend devuelve `{ "status": "running" }` pero el frontend espera
`{ "state": "in_progress" }`, el sistema se rompe. La spec de contratos
compartidos (`shared-contracts.spec.md`) existe para prevenir eso.

Cuando descubras un gap entre frontend y backend, la solución NO es
arreglar el código — es actualizar el contrato compartido y luego
re-implementar ambos lados.

---

## ⚠️ Cómo usar Claude Code para este proyecto

A diferencia de los proyectos 1 y 2, aquí conviene trabajar en sesiones separadas:

1. **Sesión Backend**: Implementa las Fases 1-3 completas
2. **Sesión Frontend**: Implementa las Fases 4-5
3. **Sesión Integración**: Fase 6 — conectar todo

Esto simula un escenario real donde las specs permiten que equipos
trabajen en paralelo sin pisarse.
