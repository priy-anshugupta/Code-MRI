# Data Persistence and Synchronization System

## Overview

The Code MRI platform now includes a comprehensive data persistence and synchronization system that stores repository intelligence data in a SQLite database. This system provides:

- **Persistent storage** for repository metadata, branch information, and analysis results
- **Conflict resolution** for concurrent updates
- **Data staleness detection** and automatic refresh mechanisms
- **Historical tracking** for trend analysis
- **Cache management** with metadata tracking

## Architecture

### Database Schema

The system uses SQLAlchemy ORM with the following tables:

1. **repositories** - Repository metadata
2. **branches** - Branch information for each repository
3. **analyses** - Analysis results for each branch/commit
4. **historical_metrics** - Time-series metrics for trend analysis
5. **cache_entries** - Cache metadata for tracking cached files

### Key Components

#### 1. DataPersistenceService (`app/services/data_persistence.py`)

Main service for storing and retrieving data from the database.

**Key Methods:**
- `store_repository()` - Store/update repository metadata
- `store_branches()` - Store/update branch information
- `store_analysis()` - Store analysis results
- `get_latest_analysis()` - Retrieve latest analysis for a branch
- `get_analysis_history()` - Get historical analysis data
- `store_historical_metric()` - Store metrics for trend analysis

#### 2. DataSynchronizationService (`app/services/data_sync.py`)

Handles concurrent updates with conflict resolution strategies.

**Conflict Resolution Strategies:**
- `LATEST_WINS` - Most recent update takes precedence (default)
- `MERGE` - Attempt to merge changes intelligently
- `MANUAL` - Require manual conflict resolution

**Key Methods:**
- `sync_branch_metadata()` - Sync branch data with conflict detection
- `sync_analysis_result()` - Sync analysis with conflict detection
- `sync_multiple_branches()` - Batch sync multiple branches
- `get_conflicts()` - Get list of unresolved conflicts
- `resolve_conflict()` - Manually resolve a conflict

#### 3. DataRefreshManager (`app/services/data_sync.py`)

Manages data staleness detection and refresh triggers.

**Key Methods:**
- `is_branch_stale()` - Check if branch data is stale
- `is_analysis_stale()` - Check if analysis is stale
- `get_stale_branches()` - Get list of stale branches
- `get_staleness_info()` - Get detailed staleness information

**Configuration:**
- Default staleness threshold: 24 hours
- Configurable per instance

#### 4. AutoRefreshService (`app/services/auto_refresh.py`)

Background service that automatically checks for and refreshes stale data.

**Features:**
- Periodic staleness checks (default: every 30 minutes)
- Optional automatic refresh triggering
- Thread-safe operation
- Status monitoring

**Key Methods:**
- `start()` - Start the auto-refresh service
- `stop()` - Stop the auto-refresh service
- `enable_auto_refresh()` - Enable automatic refresh
- `disable_auto_refresh()` - Disable automatic refresh
- `get_status()` - Get service status

#### 5. DataRefreshScheduler (`app/services/auto_refresh.py`)

Scheduler for delayed refresh operations.

**Key Methods:**
- `schedule_refresh()` - Schedule a refresh with delay
- `cancel_refresh()` - Cancel a scheduled refresh
- `get_scheduled_tasks()` - Get all scheduled tasks
- `cleanup_completed_tasks()` - Remove old completed tasks

## API Endpoints

### Data Persistence Endpoints

#### Get Repository Metadata
```
GET /persistence/repository/{repo_id}
```
Returns stored repository metadata.

#### Get Branches
```
GET /persistence/branches/{repo_id}
```
Returns all stored branches for a repository.

#### Get Analysis
```
GET /persistence/analysis/{repo_id}/{branch_name}?commit_sha={sha}
```
Returns latest analysis for a branch (optionally filtered by commit SHA).

#### Get Analysis History
```
GET /persistence/analysis-history/{repo_id}/{branch_name}?limit={limit}
```
Returns historical analysis data for a branch.

#### Get Persistence Stats
```
GET /persistence/stats
```
Returns cache and synchronization statistics.

#### Cleanup Persistence Data
```
POST /persistence/cleanup
```
Body:
```json
{
  "cleanup_old_repos": true,
  "cleanup_old_analyses": true,
  "cleanup_cache": true,
  "max_age_hours": 24,
  "max_age_days": 30
}
```

### Synchronization Endpoints

#### Get Sync Conflicts
```
GET /sync/conflicts
```
Returns list of unresolved synchronization conflicts.

#### Resolve Conflict
```
POST /sync/resolve-conflict/{conflict_index}?use_local={true|false}
```
Manually resolve a synchronization conflict.

#### Get Sync Stats
```
GET /sync/stats
```
Returns synchronization statistics.

### Data Refresh Endpoints

#### Check Branch Staleness
```
GET /refresh/staleness/{repo_id}/{branch_name}
```
Returns detailed staleness information for a branch.

#### Get Stale Branches
```
GET /refresh/stale-branches/{repo_id}
```
Returns list of stale branches for a repository.

#### Mark for Refresh
```
POST /refresh/mark/{repo_id}/{branch_name}
```
Mark a branch for refresh.

#### Schedule Refresh
```
POST /refresh/schedule/{repo_id}/{branch_name}?delay_minutes={minutes}
```
Schedule a delayed refresh for a branch.

#### Get Scheduled Tasks
```
GET /refresh/scheduled-tasks
```
Returns all scheduled refresh tasks.

#### Cancel Scheduled Refresh
```
DELETE /refresh/scheduled-tasks/{task_id}
```
Cancel a scheduled refresh task.

### Auto-Refresh Service Endpoints

#### Get Auto-Refresh Status
```
GET /auto-refresh/status
```
Returns auto-refresh service status.

#### Enable Auto-Refresh
```
POST /auto-refresh/enable
```
Enable automatic refresh of stale data.

#### Disable Auto-Refresh
```
POST /auto-refresh/disable
```
Disable automatic refresh of stale data.

## Frontend Components

### React Hooks

#### useDataFreshness
```typescript
const {
  stalenessInfo,
  refreshStatus,
  loading,
  checkStaleness,
  markForRefresh,
  triggerAnalysis
} = useDataFreshness(repoId, branchName);
```

Manages data freshness checking and refresh operations.

### Components

#### DataFreshnessIndicator
```tsx
<DataFreshnessIndicator 
  repoId={repoId} 
  branchName={branchName}
  compact={false}
/>
```

Displays data freshness status with refresh controls.

#### StaleBranchesPanel
```tsx
<StaleBranchesPanel 
  repoId={repoId}
  onRefreshBranch={(branch) => console.log('Refreshing', branch)}
/>
```

Shows list of stale branches with batch refresh capabilities.

## Usage Examples

### Storing Analysis Results

```python
from app.services.data_persistence import DataPersistenceService
from app.models.branch import BranchAnalysisResult
from datetime import datetime

persistence = DataPersistenceService()

# Store analysis
analysis = BranchAnalysisResult(
    repo_id="my-repo",
    branch_name="main",
    commit_sha="abc123",
    analysis_timestamp=datetime.now(),
    file_tree={"type": "directory"},
    technologies=["Python", "JavaScript"],
    metrics={"overall_score": 85.5},
    issues=[],
    ai_summary="Good code quality",
    detailed_scores={"overall_score": 85.5}
)

commit_sha = persistence.store_analysis(analysis)
```

### Synchronizing with Conflict Resolution

```python
from app.services.data_sync import DataSynchronizationService, ConflictResolutionStrategy

sync_service = DataSynchronizationService(
    persistence,
    ConflictResolutionStrategy.LATEST_WINS
)

# Sync branch metadata
success = sync_service.sync_branch_metadata(repo_id, branch_info)

# Check for conflicts
conflicts = sync_service.get_conflicts()
if conflicts:
    # Resolve first conflict, keeping remote data
    sync_service.resolve_conflict(0, use_local=False)
```

### Checking Data Staleness

```python
from app.services.data_sync import DataRefreshManager

refresh_manager = DataRefreshManager(persistence, stale_threshold_hours=24)

# Check if branch is stale
is_stale = refresh_manager.is_branch_stale(repo_id, branch_name)

# Get detailed staleness info
info = refresh_manager.get_staleness_info(repo_id, branch_name)
print(f"Branch is {info['age_hours']} hours old")

# Get all stale branches
stale_branches = refresh_manager.get_stale_branches(repo_id)
```

### Using Auto-Refresh Service

```python
from app.services.auto_refresh import AutoRefreshService

auto_refresh = AutoRefreshService(
    persistence,
    refresh_manager,
    check_interval_minutes=30,
    auto_refresh_enabled=True
)

# Start the service
auto_refresh.start()

# Check status
status = auto_refresh.get_status()
print(f"Auto-refresh running: {status['running']}")

# Stop when done
auto_refresh.stop()
```

## Configuration

### Database Configuration

By default, the system uses SQLite with the database file stored in the temp directory:
```
{TEMP_DIR}/code_mri.db
```

To use a different database, pass a custom database URL:
```python
persistence = DataPersistenceService("sqlite:///./custom.db")
# or
persistence = DataPersistenceService("postgresql://user:pass@localhost/dbname")
```

### Staleness Threshold

Configure how long before data is considered stale:
```python
refresh_manager = DataRefreshManager(
    persistence,
    stale_threshold_hours=12  # 12 hours instead of default 24
)
```

### Auto-Refresh Interval

Configure how often to check for stale data:
```python
auto_refresh = AutoRefreshService(
    persistence,
    refresh_manager,
    check_interval_minutes=15,  # Check every 15 minutes
    auto_refresh_enabled=True
)
```

## Testing

Run the test suite:
```bash
cd backend
python test_data_persistence.py
```

The test suite covers:
- Database setup and table creation
- Repository CRUD operations
- Branch CRUD operations
- Analysis storage and retrieval
- Synchronization with conflict resolution
- Data refresh management

## Performance Considerations

1. **Database Indexes**: All tables have appropriate indexes for common queries
2. **Session Management**: Sessions are properly closed to prevent connection leaks
3. **Batch Operations**: Use `sync_multiple_branches()` for bulk operations
4. **Cache Cleanup**: Regularly cleanup old cache entries to save space
5. **Historical Data**: Limit historical data retention with cleanup operations

## Troubleshooting

### Database Locked Errors

If you encounter "database is locked" errors with SQLite:
- Ensure only one process is writing at a time
- Consider using PostgreSQL for production
- Increase timeout in database URL: `sqlite:///./db.db?timeout=20`

### Session Detached Errors

If you see "Instance is not bound to a Session" errors:
- The service methods return dictionaries or primitives to avoid session issues
- Don't try to access ORM object attributes after session is closed

### Stale Data Not Refreshing

If auto-refresh isn't working:
- Check that auto-refresh is enabled: `GET /auto-refresh/status`
- Verify the service is running
- Check logs for errors in the refresh loop
- Ensure the async analysis pipeline is running

## Future Enhancements

Potential improvements for the data persistence system:

1. **PostgreSQL Support**: Full production-ready PostgreSQL configuration
2. **Data Migration Tools**: Alembic integration for schema migrations
3. **Backup/Restore**: Automated backup and restore functionality
4. **Data Archival**: Archive old analysis data to separate storage
5. **Replication**: Multi-node database replication for high availability
6. **Query Optimization**: Advanced query optimization and caching
7. **Metrics Dashboard**: Real-time dashboard for persistence metrics
