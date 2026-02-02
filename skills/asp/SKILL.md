---
name: asp
description: This skill should be used when the user asks to "manage stream processors", "list processors", "start processor", "stop processor", "show workspaces", or discusses MongoDB Atlas Stream Processing, ASP pipelines, or streaming data workloads.
version: 1.0.0
---

# MongoDB Atlas Stream Processing

This skill manages MongoDB Atlas Stream Processing (ASP) pipelines using the `sp` CLI tool. Use natural language to create, deploy, monitor, and optimize streaming data workloads.

## Running Commands

Use this path pattern for all sp commands:
```bash
~/.claude/plugins/cache/asp-skill/asp/*/tools/sp/sp <command>
```

## Quick Reference

| Action | Command |
|--------|---------|
| List workspaces | `~/.claude/plugins/cache/asp-skill/asp/*/tools/sp/sp workspaces list` |
| List processors | `~/.claude/plugins/cache/asp-skill/asp/*/tools/sp/sp processors list` |
| Start processor | `~/.claude/plugins/cache/asp-skill/asp/*/tools/sp/sp processors start -p <name> --auto` |
| Stop processor | `~/.claude/plugins/cache/asp-skill/asp/*/tools/sp/sp processors stop -p <name>` |
| Get stats | `~/.claude/plugins/cache/asp-skill/asp/*/tools/sp/sp processors stats -p <name>` |
| Tier advice | `~/.claude/plugins/cache/asp-skill/asp/*/tools/sp/sp processors tier-advise -p <name>` |

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

### Collection Management (Data Verification)
| Command | Description |
|---------|-------------|
| `sp collections count -c db.collection` | Count documents in a collection |
| `sp collections query -c db.collection -l 10` | Query documents (limit 10) |
| `sp collections query -c db.collection -f '{"status":"active"}'` | Query with filter |
| `sp collections list -d dbname` | List all collections in database |
| `sp collections ttl -c db.collection -s 3600 -f _ts` | Set TTL index (1 hour) |
| `sp collections index -c db.collection --list` | List indexes on collection |

### Materialized Views
| Command | Description |
|---------|-------------|
| `sp materialized_views list` | List all materialized views |
| `sp materialized_views create <name>` | Create a materialized view |
| `sp materialized_views drop <name>` | Drop a materialized view |

## Creating Processors

**IMPORTANT**: Before creating any processor, consult the official MongoDB ASP examples repo for best practices and valid patterns:

https://github.com/mongodb/ASP_example

This repo contains the latest source/sink configurations, valid pipeline stages, and working examples. Always fetch and review examples from this repo when:
- Creating new processors
- Configuring sources (Kafka, Atlas change streams, etc.)
- Setting up sinks ($merge targets)
- Using advanced features ($lookup, $function, windowing)

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

### $source Configuration

**Always consult https://github.com/mongodb/ASP_example for current source configurations.**

Key points:
- **Kafka sources REQUIRE a `topic` field**
- **HTTP connections are NOT sources** - they are for lookups/enrichment only
- Not all connection types are valid sources

Fetch examples from the ASP_example repo before creating processors to ensure correct syntax.

### IMPORTANT: Invalid Variables

`$$NOW`, `$$ROOT`, `$$CURRENT` and similar MongoDB aggregation system variables are **NOT valid in Atlas Stream Processing pipelines**. Do not use them.

For timestamps, use the `$source` timeField or pass timestamps from your data source.

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
4. `sp processors stats -p <name>` - Check for DLQ errors
5. `sp collections count -c <db>.<output_collection>` - Verify data is flowing

### Verify Data Flow
After starting a processor with `$merge`, verify data reaches the destination:
1. `sp processors stats -p <name>` - Check inputMessageCount > 0 and dlqMessageCount = 0
2. `sp collections count -c mydb.output` - Confirm documents in target collection
3. `sp collections query -c mydb.output -l 5` - Sample documents to verify structure

**If count is 0 but stats show input:**
- Check DLQ for errors: `sp collections query -c <dlq_db>.<dlq_coll> -l 10`
- Verify `$merge` connectionName matches a valid cluster connection
- Check field mappings in pipeline stages

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

## Reference Documentation

The `docs/` directory contains comprehensive guides:
- **PIPELINE_PATTERNS.md** - Common pipeline patterns and examples
- **CONNECTION_GUIDE.md** - Connection types and configuration
- **PROCESSOR_SIZING_GUIDE.md** - Tier selection and sizing
- **SP_USER_MANUAL.md** - Complete sp CLI reference
- **ATLAS_STREAM_PROCESSING_PARALLELISM.md** - Parallelism configuration
- **TESTING_GUIDE.md** - Testing and validation

Consult these docs when building complex processors.

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
