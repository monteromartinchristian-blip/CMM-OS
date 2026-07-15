# CMM OS

CMM OS (Code Management Machine Operating System) is an AI-native software development operating system.

Instead of allowing an LLM to directly modify files, CMM OS translates user intent into structured execution plans that are validated and executed by a semantic kernel.

## Features

- Semantic execution plans
- Python AST editing
- Modular execution kernel
- Tool-based architecture
- Ollama integration
- Architecture-aware planning

## Current capabilities

- Create files
- Read files
- Create directories
- Replace text blocks
- Insert text before/after anchors
- Insert Python methods semantically

## Project structure

```
CMM-OS/
├── cmm/
├── cmm_agent/
├── kernel/
├── runtime/
├── scripts/
├── docs/
├── README.md
├── requirements.txt
└── .gitignore
```

## Installation

Clone the repository:

```bash
git clone https://github.com/monteromartinchristian-blip/CMM-OS.git

cd CMM-OS
```

Create a virtual environment:

```bash
python3 -m venv .venv
```

Activate it:

```bash
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Running

Generate a plan:

```bash
cmm plan "Your objective"
```

Apply the plan:

```bash
cmm apply
```

## Roadmap

Current semantic actions:

- ✅ python.insert_method

Planned:

- python.replace_method
- python.delete_method
- python.rename_method
- python.add_import
- python.remove_import
- python.create_class
- python.replace_class

## License

Private project.