# MongoDB Atlas Stream Processing Plugin (Development)

This is the **development repository** for the ASP Claude Code plugin.

## For Users
Install via: `/plugin marketplace add kgorman/asp_claude` then `/plugin install asp@kgorman`

## For Development
When working in this repo, use `./tools/sp` directly. The plugin structure is in `.claude-plugin/` and `skills/`.

---

This plugin provides an AI-friendly CLI toolkit for managing MongoDB Atlas Stream Processing (ASP) pipelines with natural language.

## Overview

Atlas Stream Processing allows you to build real-time data pipelines that process streaming data using MongoDB's aggregation framework. This skill follows the **"processors are files"** philosophy where each JSON file represents a self-contained, deployable pipeline.

## Quick Start

### Prerequisites
- Python 3.7+
- MongoDB Atlas account with Stream Processing enabled
- Atlas API credentials (Public/Private key pair)

### Setup

1. **Configure credentials** - Copy `config.txt.example` to `config.txt` and fill in:
   ```
   PUBLIC_KEY=your_atlas_public_key
   PRIVATE_KEY=your_atlas_private_key
   PROJECT_ID=your_atlas_project_id
   SP_WORKSPACE_NAME=your_workspace_name
   ```

2. **Install dependencies**:
   ```bash
   pip install -r tools/requirements.txt
   ```

3. **Make sp executable**:
   ```bash
   chmod +x tools/sp
   ```

## Directory Structure

```
asp_claude/
├── CLAUDE.md              # This file - skill instructions for Claude
├── config.txt.example     # API credentials template (never commit actual config.txt)
├── tools/
│   ├── sp                 # Main CLI tool
│   ├── atlas_api.py       # Atlas Stream Processing API wrapper
│   └── requirements.txt   # Python dependencies
├── processors/            # Stream processor JSON definitions
│   └── *.json            # Each file is a deployable processor
├── connections/           # Connection configurations
│   └── connections.json   # Database and service connections
└── docs/                  # Comprehensive documentation
```

## Core Commands

### Workspace Management
```bash
# List all workspaces
./tools/sp workspaces list

# Create a workspace
./tools/sp workspaces create <name> --cloud-provider AWS --region US_EAST_1

# Get workspace details
./tools/sp workspaces details <name>

# Delete a workspace
./tools/sp workspaces delete <name>
```

### Connection Management
```bash
# Create connections from connections.json
./tools/sp instances connections create

# List connections
./tools/sp instances connections list

# Test connections (with MongoDB verification)
./tools/sp instances connections test

# Delete a connection
./tools/sp instances connections delete <connection_name>
```

### Processor Management
```bash
# Create all processors from processors/ directory
./tools/sp processors create

# Create specific processor
./tools/sp processors create -p <processor_name>

# List processors with status and tier info
./tools/sp processors list

# Start a processor (auto-selects optimal tier)
./tools/sp processors start -p <processor_name> --auto

# Start with specific tier
./tools/sp processors start -p <processor_name> -t SP10

# Stop a processor
./tools/sp processors stop -p <processor_name>

# Get processor statistics
./tools/sp processors stats -p <processor_name>

# Get tier recommendation
./tools/sp processors tier-advise -p <processor_name>

# Delete a processor
./tools/sp processors drop -p <processor_name>
```

### Performance Profiling
```bash
# Profile a processor for 5 minutes
./tools/sp processors profile -p <processor_name> --duration 300

# Continuous monitoring
./tools/sp processors profile -p <processor_name> --continuous

# Profile with custom metrics
./tools/sp processors profile -p <processor_name> --metrics memory,latency,throughput
```

## Creating Processors

Processors are defined as JSON files in the `processors/` directory. Each file should contain:

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
            "$match": {
                "value": { "$gt": 100 }
            }
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

- **$source** - Define data source (HTTP, Kafka, or cluster connection)
- **$match** - Filter documents
- **$project** - Select/transform fields
- **$addFields** - Add computed fields
- **$group** - Aggregate data
- **$window** - Window-based computations
- **$function** - Custom JavaScript transformations
- **$merge** - Write to destination

## Tier Selection

The `sp` CLI can automatically recommend optimal tiers based on pipeline complexity:

| Tier | Use Case |
|------|----------|
| SP2  | Very simple pipelines (<10 complexity) |
| SP5  | Simple pipelines with basic filtering |
| SP10 | Moderate complexity, joins, grouping |
| SP30 | Complex pipelines with windows/functions |
| SP50 | High parallelism, multiple complex operations |

Use `--auto` flag to let the tool analyze and select the optimal tier.

## Connections

Define connections in `connections/connections.json`:

```json
{
  "connections": [
    {
      "name": "Cluster01",
      "type": "Cluster",
      "clusterName": "MyAtlasCluster",
      "dbRoleToExecute": {
        "role": "atlasAdmin",
        "type": "BUILT_IN"
      }
    },
    {
      "name": "my_http_source",
      "type": "https",
      "url": "https://api.example.com/stream"
    }
  ]
}
```

## Common Workflows

### Deploy a New Processor
1. Create processor JSON in `processors/`
2. Run `./tools/sp processors create -p <name>`
3. Run `./tools/sp processors start -p <name> --auto`
4. Monitor with `./tools/sp processors stats -p <name>`

### Troubleshoot Performance
1. Check status: `./tools/sp processors list`
2. Get stats: `./tools/sp processors stats -p <name> --verbose`
3. Profile: `./tools/sp processors profile -p <name> --duration 300`
4. Get tier advice: `./tools/sp processors tier-advise -p <name>`

### Update a Processor
1. Stop: `./tools/sp processors stop -p <name>`
2. Edit the JSON file in `processors/`
3. Drop old: `./tools/sp processors drop -p <name>`
4. Create new: `./tools/sp processors create -p <name>`
5. Start: `./tools/sp processors start -p <name> --auto`

## Environment Variables

- `MONGODB_CONNECTION_STRING` - Required for connection testing with MongoDB native driver verification

## Output Format

All commands output colorized JSON for easy parsing by AI assistants. Example:
```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "operation": "start_processor",
  "status": "success",
  "processor": "my_processor",
  "tier": "SP10"
}
```

## Error Handling

The tool provides detailed error messages with:
- HTTP status codes
- API error details
- Suggested fixes
- Fallback tier recommendations when validation fails

## Best Practices

1. **Version control processors** - Each processor is a file, perfect for Git
2. **Use descriptive names** - Processor names should indicate their function
3. **Start with --auto** - Let the tool recommend optimal tiers
4. **Test connections first** - Always verify connections before deploying processors
5. **Monitor with profiling** - Use continuous monitoring for production workloads
