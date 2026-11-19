# User Flows

## 1. Member flow

```mermaid
flowchart TD
    A[Open Member Portal] --> B[Mock Login as Member]
    B --> C[Member Dashboard]
    C --> D{Choose action}
    D -->|Raise ticket| E[Select category]
    E --> F[Enter issue description]
    F --> G[Submit ticket]
    G --> H[System assigns ticket ID]
    H --> I[System applies admin category-priority rule]
    I --> J[System creates SLA deadline]
    J --> K[Ticket appears in My Tickets]
    D -->|View tickets| L[My Tickets list]
    L --> M[Open ticket details]
    M --> N[View replies, status and timeline]
    N --> O{Ticket status}
    O -->|In Progress / Open| P[Reply to support]
    O -->|Resolved| Q{Member satisfied?}
    Q -->|Yes| R[Confirm resolution]
    R --> S[Ticket Closed]
    Q -->|No| T[Reopen with mandatory reason]
    T --> U[Ticket Reopened; SLA resumes/restarts per policy]
```

### Member screens
1. Login / demo role selection
2. Member dashboard with ticket counts and recent tickets
3. Raise ticket form
4. My Tickets list with status, category, priority and created date
5. Ticket detail with threaded replies and action controls
6. Resolution confirmation and reopen-reason dialog

## 2. Support Agent flow

```mermaid
flowchart TD
    A[Open Support Workspace] --> B[Mock Login as Support Agent]
    B --> C[Support Queue]
    C --> D[Filter by status, category, priority or overdue]
    C --> E[Search by ticket ID or member]
    D --> F[Open ticket]
    E --> F
    F --> G{Assigned?}
    G -->|No| H[Assign to self / permitted agent]
    G -->|Yes| I[Review ticket]
    H --> I
    I --> J[Read member conversation and history]
    J --> K{Next action}
    K -->|Reply| L[Send reply]
    K -->|Change priority| M[Select priority and enter reason]
    K -->|Request information| N[Mark SLA as waiting on member]
    K -->|Resolve| O[Mark ticket Resolved]
    L --> P[Update ticket timeline]
    M --> P
    N --> P
    O --> P
    P --> C
```

### Support Agent screens
1. Queue overview with KPI cards
2. Filterable/searchable ticket table
3. Ticket detail and conversation thread
4. Assignment control
5. Reply composer
6. Priority-change dialog with mandatory reason
7. Resolve action

## 3. Support Head / Admin flow

```mermaid
flowchart TD
    A[Open Admin Workspace] --> B[Mock Login as Support Head]
    B --> C[Admin Dashboard]
    C --> D[Monitor open, overdue, escalated and resolved-today]
    C --> E[Open escalated queue]
    E --> F[Review ticket, SLA and history]
    F --> G[Reassign / guide agent / monitor resolution]
    C --> H[Configuration]
    H --> I[Configure category-to-default-priority mapping]
    H --> J[Configure TAT hours by priority]
    H --> K[Configure reopen window and max attempts]
    I --> L[Save configuration]
    J --> L
    K --> L
    L --> M[Audit configuration change]
```

### Support Head screens
1. Admin dashboard and analytics
2. Escalated ticket queue
3. Ticket detail with full audit history
4. Category priority configuration
5. Priority-based TAT configuration
6. Reopen policy configuration

## 4. Escalation and SLA flow

```mermaid
flowchart TD
    A[Ticket created or SLA restarted] --> B[Calculate due_at from priority TAT]
    B --> C[Scheduler checks active SLA records]
    C --> D{SLA paused?}
    D -->|Yes| C
    D -->|No| E{Unresolved and current time > due_at?}
    E -->|No| C
    E -->|Yes| F[Mark ticket Escalated]
    F --> G[Preserve previous workflow status]
    G --> H[Write immutable history event]
    H --> I[Create in-app notification for Support Head]
```

## 5. Key navigation map

- Member: Dashboard → Raise Ticket / My Tickets → Ticket Detail
- Agent: Queue → Ticket Detail → Reply / Assign / Resolve
- Support Head: Dashboard → Escalated Queue / Configuration → Ticket Detail
