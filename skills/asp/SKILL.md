---
name: asp
description: This skill should be used when the user asks to "manage stream processors", "list processors", "start processor", "stop processor", "show workspaces", or discusses MongoDB Atlas Stream Processing, ASP pipelines, or streaming data workloads.
version: 1.0.0
---

# MongoDB Atlas Stream Processing

This skill manages MongoDB Atlas Stream Processing (ASP) pipelines using the `sp` CLI tool. Use natural language to create, deploy, monitor, and optimize streaming data workloads.

## Plugin Location

When this plugin is installed, the tools are located at:
`~/.claude/plugins/asp/tools/sp`

Set the plugin path variable for commands:
```bash
ASP_DIR="$HOME/.claude/plugins/asp"
```

## Quick Reference

### List workspaces
```bash
$ASP_DIR/tools/sp workspaces list
```

### List processors
```bash
$ASP_DIR/tools/sp processors list
```

### Start a processor (auto-select tier)
```bash
$ASP_DIR/tools/sp processors start -p <name> --auto
```

### Stop a processor
```bash
$ASP_DIR/tools/sp processors stop -p <name>
```

### Get processor stats
```bash
$ASP_DIR/tools/sp processors stats -p <name>
```

### Get tier recommendation
```bash
$ASP_DIR/tools/sp processors tier-advise -p <name>
```

## Setup Requirements

Before using, ensure the plugin has a valid `config.txt` in its directory:
```
PUBLIC_KEY=your_atlas_public_key
PRIVATE_KEY=your_atlas_private_key
PROJECT_ID=your_atlas_project_id
SP_WORKSPACE_NAME=your_workspace_name
```

Copy from `config.txt.example` and fill in your Atlas API credentials.

## Core Commands

### Workspace Management
| Command | Description |
|---------|-------------|
| `sp workspaces list` | List all Stream Processing workspaces |
| `sp workspaces create <name>` | Create a new workspace |
| `sp workspaces details <name>` | Get workspace details |
| `sp workspaces delete <name>` | Delete a workspace |

### Processor Management
| Command | Description |
|---------|-------------|
| `sp processors list` | List all processors with status/tier |
| `sp processors create -p <name>` | Create processor from JSON file |
| `sp processors start -p <name> --auto` | Start with auto tier selection |
| `sp processors start -p <name> -t SP10` | Start with specific tier |
| `sp processors stop -p <name>` | Stop a processor |
| `sp processors stats -p <name>` | Get processor statistics |
| `sp processors tier-advise -p <name>` | Get tier recommendation |
| `sp processors drop -p <name>` | Delete a processor |

### Connection Management
| Command | Description |
|---------|-------------|
| `sp instances connections list` | List connections |
| `sp instances connections create` | Create from connections.json |
| `sp instances connections test` | Test connections |
| `sp instances connections delete <name>` | Delete a connection |

### Performance Profiling
| Command | Description |
|---------|-------------|
| `sp processors profile -p <name> --duration 300` | Profile for 5 minutes |
| `sp processors profile -p <name> --continuous` | Continuous monitoring |

## Creating Processors

Processors are JSON files defining streaming pipelines:

```json
{
    "name": "my_processor",
    "pipeline": [
        {
            "$source": {
                "connectionName": "my_connection",
                "timeField": { "$dateFromString": { "dateString": "$timestamp" }}
            }
        },
        {
            "$match": { "value": { "$gt": 100 } }
        },
        {
            "$merge": {
                "into": {
                    "connectionName": "Cluster01",
                    "db": "mydb",
                    "coll": "output"
                }
            }
        }
    ]
}
```

### Pipeline Stages
- **$source** - Data source (HTTP, Kafka, cluster)
- **$match** - Filter documents
- **$project** - Select/transform fields
- **$addFields** - Add computed fields
- **$group** - Aggregate data
- **$window** - Window-based computations
- **$function** - Custom JavaScript transformations
- **$merge** - Write to destination

## Tier Selection

| Tier | Use Case |
|------|----------|
| SP2 | Very simple pipelines |
| SP5 | Simple pipelines with basic filtering |
| SP10 | Moderate complexity, joins, grouping |
| SP30 | Complex pipelines with windows/functions |
| SP50 | High parallelism, multiple complex operations |

Use `--auto` to let the tool analyze and select the optimal tier.

## Common Workflows

### Deploy a New Processor
1. Create processor JSON in `processors/`
2. `sp processors create -p <name>`
3. `sp processors start -p <name> --auto`
4. `sp processors stats -p <name>`

### Troubleshoot Performance
1. `sp processors list` - Check status
2. `sp processors stats -p <name> --verbose` - Get detailed stats
3. `sp processors profile -p <name> --duration 300` - Profile
4. `sp processors tier-advise -p <name>` - Get tier advice

### Update a Processor
1. `sp processors stop -p <name>`
2. Edit the JSON file
3. `sp processors drop -p <name>`
4. `sp processors create -p <name>`
5. `sp processors start -p <name> --auto`

## Output Format

All commands output JSON for easy parsing:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "operation": "start_processor",
  "status": "success",
  "processor": "my_processor",
  "tier": "SP10"
}
```
