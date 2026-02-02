# MongoDB Atlas Stream Processing Plugin for Claude Code

A Claude Code plugin for managing MongoDB Atlas Stream Processing (ASP) pipelines with natural language.

## Installation

```bash
# Add the marketplace
/plugin marketplace add kgorman/asp_claude

# Install the plugin
/plugin install asp@kgorman
```

## Setup

After installation, configure your Atlas API credentials:

```bash
# Navigate to the plugin directory
cd ~/.claude/plugins/asp

# Copy and edit the config file
cp config.txt.example config.txt
# Edit config.txt with your credentials
```

Required credentials (get from Atlas UI):
- `PUBLIC_KEY` - Atlas API public key
- `PRIVATE_KEY` - Atlas API private key
- `PROJECT_ID` - Your Atlas project ID
- `SP_WORKSPACE_NAME` - Stream Processing workspace name

## Usage

Once installed, use the `/asp` skill or just ask Claude naturally:

- "Show me my stream processing workspaces"
- "List all running processors"
- "Start the solar_processor with auto tier selection"
- "What tier should I use for my_processor?"
- "Stop all processors"

## Features

- **Workspace Management** - Create, list, delete ASP workspaces
- **Processor Lifecycle** - Create, start, stop, restart processors
- **Auto Tier Selection** - Analyzes pipeline complexity and recommends optimal tier
- **Performance Profiling** - Monitor processor metrics over time
- **Connection Management** - Manage data source and sink connections

## Tiers

| Tier | Use Case |
|------|----------|
| SP2 | Very simple pipelines |
| SP5 | Simple filtering |
| SP10 | Joins, grouping |
| SP30 | Windows, functions |
| SP50 | High parallelism |

## Requirements

- Python 3.7+
- MongoDB Atlas account with Stream Processing enabled
- Atlas API credentials

## License

Apache 2.0
