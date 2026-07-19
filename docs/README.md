# Engineering Documentation

A complete, reverse-engineered account of how this project was built, how every layer works, and how to talk about it in an interview. Written to be accurate to the actual codebase and deployment — not a generic template.

| # | Document | Covers |
|---|---|---|
| 01 | [Project Overview](01_Project_Overview.md) | What this is, the problem it solves, high-level facts |
| 02 | [System Architecture](02_System_Architecture.md) | Layers, design patterns, data model |
| 03 | [Tech Stack](03_Tech_Stack.md) | Every dependency and why it was chosen |
| 04 | [Project Structure](04_Project_Structure.md) | Folder-by-folder, file-by-file |
| 05 | [Backend](05_Backend.md) | FastAPI, routers, DI, Pydantic, error handling, logging |
| 06 | [Frontend](06_Frontend.md) | The actual vanilla HTML/JS `/ui` page (not React/Vite/TS) |
| 07 | [RAG Pipeline](07_RAG_Pipeline.md) | Conceptual walkthrough with real examples |
| 08 | [LangChain](08_LangChain.md) | What it provides, where it's used |
| 09 | [LangGraph](09_LangGraph.md) | The state graph, nodes, conditional edges, retry loop |
| 10 | [Vector Database](10_Vector_Database.md) | Embeddings, cosine similarity, Chroma/FAISS |
| 11 | [APIs](11_APIs.md) | Every endpoint, purpose, flow, error cases |
| 12 | [Authentication](12_Authentication.md) | JWT, bcrypt, the auth dependency |
| 13 | [Docker](13_Docker.md) | Multi-stage build, compose topology, line-by-line |
| 14 | [AWS Deployment](14_AWS_Deployment.md) | IAM, EC2, networking, TLS, DNS, scaling |
| 15 | [GitHub Actions](15_GitHub_Actions.md) | ci.yml and cd.yml, line-by-line |
| 16 | [Security](16_Security.md) | Threat model, what's covered, named gaps |
| 17 | [Performance](17_Performance.md) | Where the real costs are, trade-offs made |
| 18 | [Debugging Journal](18_Debugging.md) | 9 real incidents — symptom, root cause, fix, lesson |
| 19 | [Interview Preparation](19_Interview_Preparation.md) | 90 Q&A + resume mapping |
| 20 | [Non-Technical Explanations](20_Non_Technical_Explanation.md) | The same project, explained to 9 different audiences |

`Architecture_Diagrams/` holds Mermaid source for every diagram referenced above — renders natively on GitHub.

## A note on accuracy

This documentation set was written by re-reading the actual source files (not from memory of a generic template), and corrects one common assumption head-on: the frontend is **not** React/Vite/TypeScript — it's a single static HTML/JS file. See `06_Frontend.md` for why, and for what it would take to actually become a framework-based frontend if that were ever needed.
