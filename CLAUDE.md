# MongoDB Atlas Stream Processing Plugin (Development)

This is the **development repository** for the ASP Claude Code plugin.

## For Users
Install via: `/plugin marketplace add kgorman/asp_claude` then `/plugin install asp@kgorman`

## For Development
When working in this repo, use `./tools/sp/sp` directly. The plugin structure is in `.claude-plugin/` and `skills/`.

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
   pip install -r tools/sp/requirements.txt
   ```

3. **Make sp executable**:
   ```bash
   chmod +x tools/sp/sp
   ```

## Directory Structure

```
asp_claude/
├── CLAUDE.md              # This file - skill instructions for Claude
├── config.txt.example     # API credentials template (never commit actual config.txt)
├── tools/
│   └── sp/                # Stream processing CLI toolkit
│       ├── sp             # Main CLI tool
│       ├── atlas_api.py   # Atlas Stream Processing API wrapper
│       ├── requirements.txt # Python dependencies
│       ├── sp-schema.json # JSON schema for tool
│       └── sp.yaml        # Tool metadata
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
./tools/sp/sp workspaces list

# Create a workspace
./tools/sp/sp workspaces create <name> --cloud-provider AWS --region US_EAST_1

# Get workspace details
./tools/sp/sp workspaces details <name>

# Delete a workspace
./tools/sp/sp workspaces delete <name>
```

### Connection Management
```bash
# Create connections from connections.json
./tools/sp/sp instances connections create

# List connections
./tools/sp/sp instances connections list

# Test connections (with MongoDB verification)
./tools/sp/sp instances connections test

# Delete a connection
./tools/sp/sp instances connections delete <connection_name>
```

### Processor Management
```bash
# Create all processors from processors/ directory
./tools/sp/sp processors create

# Create specific processor
./tools/sp/sp processors create -p <processor_name>

# List processors with status and tier info
./tools/sp/sp processors list

# Start a processor (auto-selects optimal tier)
./tools/sp/sp processors start -p <processor_name> --auto

# Start with specific tier
./tools/sp/sp processors start -p <processor_name> -t SP10

# Stop a processor
./tools/sp/sp processors stop -p <processor_name>

# Get processor statistics
./tools/sp/sp processors stats -p <processor_name>

# Get tier recommendation
./tools/sp/sp processors tier-advise -p <processor_name>

# Delete a processor
./tools/sp/sp processors drop -p <processor_name>
```

### Performance Profiling
```bash
# Profile a processor for 5 minutes
./tools/sp/sp processors profile -p <processor_name> --duration 300

# Continuous monitoring
./tools/sp/sp processors profile -p <processor_name> --continuous

# Profile with custom metrics
./tools/sp/sp processors profile -p <processor_name> --metrics memory,latency,throughput
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

##  Logic Guardrails & Architectural Rules (CRITICAL)
Claude must strictly adhere to these constraints when generating or editing JSON in the `processors/` directory.

### Prohibited Operators & ASP Limitations
Claude must never suggest the following stages. If a user's request seems to require them, use the recommended ASP-native alternative:

| Unsupported Stage | Why it's blocked | ASP-Native Alternative |
| :--- | :--- | :--- |
| **$facet** | Branching is not supported | Create multiple processor files. |
| **$out** | Not designed for streams | Use **$merge** (Atlas) or **$emit** (Kafka). |
| **$lookup** (to Kafka) | $lookup only targets Atlas | Use multiple **$source** topics if supported. |
| **$graphLookup** | Recursive logic too high-latency | Use flat **$lookup** or pre-calculate. |
| **$indexStats** | Operational stage | Use the **sp processors stats** CLI command. |
| **Unbounded $sort** | Memory exhaustion risk | Use **$sort** strictly inside a **$window**. |

### The "Linear" Rule
- **One Source, One Sink:** Every pipeline MUST start with exactly one $source stage and end with exactly one sink stage ($emit or $merge).
- **No Branching:** $facet is NOT supported. ASP pipelines are strictly linear.
- **Side Outputs:** To achieve parallel processing paths, define **multiple separate processor files** reading from the same source.


### Enrichment Strategy
* **Multiple Lookups:** While only one `$source` (the trigger) is allowed, a pipeline can contain multiple `$lookup` or `$cachedLookup` stages for data enrichment.
* **Lookup Choice:** Use `$lookup` for real-time accuracy; use `$cachedLookup` for high-performance reference data (requires SP30+ tier).

### General Architectural Mapping (The "Pivot" Logic)
When translating general stream processing concepts (from SQL, Flink, or Spark) into ASP, follow these fundamental transformations:

* **Continuous Patterns over Rows:** ASP does not use SQL-style pattern matching. Instead, utilize **$match** for simple filters and **$window** (specifically windowed pipelines) for stateful pattern detection.
* **Time Management (Watermarking):** ASP manages "lateness" and "idleness" within the **$window** stage configuration. Use `idleTimeout` and `expireAfter` to handle late-arriving data.
* **Data Partitioning:** Concepts like `KeyBy` or `PartitionBy` must be mapped to the **partitionBy** field within $window or as part of an initial **$group** if the operation is bounded.
* - **Data Joins:** Stream-to-Static joins must be implemented via **$lookup** or **$cachedLookup**. Stream-to-Stream joins are currently out-of-scope for single processors and should be handled via source-level merging or multiple processors.
* - **Output Branching:** If the logic requires "Side Outputs" or "Splitting," you must implement **Multiple Linear Processors** reading from the same source topic.

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
2. Run `./tools/sp/sp processors create -p <name>`
3. Run `./tools/sp/sp processors start -p <name> --auto`
4. Monitor with `./tools/sp/sp processors stats -p <name>`

### Troubleshoot Performance
1. Check status: `./tools/sp/sp processors list`
2. Get stats: `./tools/sp/sp processors stats -p <name> --verbose`
3. Profile: `./tools/sp/sp processors profile -p <name> --duration 300`
4. Get tier advice: `./tools/sp/sp processors tier-advise -p <name>`

### Update a Processor
1. Stop: `./tools/sp/sp processors stop -p <name>`
2. Edit the JSON file in `processors/`
3. Drop old: `./tools/sp/sp processors drop -p <name>`
4. Create new: `./tools/sp/sp processors create -p <name>`
5. Start: `./tools/sp/sp processors start -p <name> --auto`

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
