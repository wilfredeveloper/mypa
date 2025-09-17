# Complete Enhanced Personal Assistant Agent Instructions

## Overview and Architecture

The personal assistant agent requires a sophisticated meta-cognitive layer that can handle complex multi-tool scenarios. Based on the analysis of the conversation logs where the agent successfully created a calendar event but failed to send the email with the calendar link, we need to implement a comprehensive planning and execution system.

The agent must start with reasoning about the user's intent to identify what is needed to achieve the user's goal. When the user's intent involves more than one tool, the agent should use a planning tool to create a systematic approach to achieve the user's goal.

## Core Architecture: Four-Phase Execution Model

### Phase 1: Meta-Cognitive Thinking
The agent must first analyze and decompose the user's request before taking any action.

**Thinking Process:**
1. Analyze user intent and identify end goal
2. Determine complexity level (single vs multi-tool requirement)
3. Classify planning type (Procedural vs Domain Planning)
4. Identify required tools and dependencies
5. Save structured analysis to `thoughts.txt`

**Planning Type Classification:**

**Type 1: Procedural Planning (How to execute)**
- User gives a clear goal
- Agent plans the execution steps
- Focus: "How do I accomplish this?"
- Example: "Setup a meeting and send invitations"

**Type 2: Domain Planning (What the plan should contain)**
- User asks for a plan to be created
- Agent plans the content/strategy
- Focus: "What should the plan include?"
- Example: "Create a 30-day workout plan"

### Phase 2: Strategic Planning
After the thinking phase identifies the approach needed, create a detailed execution plan.

**Planning Requirements:**
- Show the agent ALL available tools
- Include conversation history
- Reference collected tool entities if needed
- Write a series of tasks to achieve the end goal
- Save comprehensive plan to `plan.txt`

### Phase 3: Systematic Execution
Execute the plan step-by-step with continuous evaluation.

**Execution Flow:**
1. Retrieve current plan from `plan.txt`
2. Execute next pending step
3. Evaluate step completion using LLM
4. Update plan status and results
5. Continue until all steps completed

**Step Evaluation Criteria:**
- Did the tool execute successfully?
- Does the result meet the expected outcome?
- Are we progressing toward the user's goal?
- Should the step be marked complete or require retry?

### Phase 4: Final Evaluation
After all tasks are completed, evaluate overall success.

**Final Assessment:**
- Compare results against original user goal
- Identify any incomplete or failed tasks
- Report problems encountered
- Confirm user satisfaction
- Present comprehensive results

## Virtual File System (VFS) Implementation

### Mandatory Session Files
At every new session creation, automatically create three core files:

#### 1. thoughts.txt Structure
```
SESSION: [session_id]
CREATED: [timestamp]
USER_TIMEZONE: [timezone]
USER_ID: [user_id]

=== INITIAL ANALYSIS ===
USER_REQUEST: [exact user request]
PRIMARY_GOAL: [main objective identified]
COMPLEXITY_LEVEL: [Single Tool/Multi-Tool/Complex Multi-Tool]
PLANNING_TYPE: [Procedural/Domain/Hybrid]
REQUIRED_TOOLS: [list of tools needed]
ESTIMATED_STEPS: [number of steps anticipated]

=== THINKING LOG ===
[TIMESTAMP] GOAL_DECOMPOSITION: [broken down sub-goals]
[TIMESTAMP] DEPENDENCIES_IDENTIFIED: [tool dependencies and order]
[TIMESTAMP] RISK_ASSESSMENT: [potential issues or blockers]
[TIMESTAMP] SUCCESS_CRITERIA: [how to measure completion]

=== ONGOING THOUGHTS ===
[Add new analytical thoughts below with timestamps]
```

#### 2. plan.txt Structure
```
SESSION: [session_id]
PLAN_TYPE: [Procedural/Domain/Hybrid]
CREATED: [timestamp]
LAST_UPDATED: [timestamp]
OVERALL_STATUS: [Planning/In Progress/Completed/Failed/Paused]

=== PLAN OVERVIEW ===
PRIMARY_GOAL: [main user objective]
SUCCESS_DEFINITION: [what constitutes success]
ESTIMATED_DURATION: [time estimate]
TOOLS_REQUIRED: [comprehensive tool list]
CRITICAL_DEPENDENCIES: [must-complete-first items]

=== EXECUTION STEPS ===

STEP 1: [descriptive step name]
DESCRIPTION: [detailed step description]
STATUS: [Pending/In Progress/Completed/Failed/Skipped]
TOOL_REQUIRED: [specific tool name]
PARAMETERS: [tool parameters/configuration]
DEPENDENCIES: [previous steps that must complete first]
STARTED_AT: [timestamp]
COMPLETED_AT: [timestamp]
EXECUTION_TIME: [duration]
RESULT_SUMMARY: [brief result description]
DETAILED_RESULT: [full tool response]
EVALUATION: [success/failure assessment]
NOTES: [additional context or issues]

STEP 2: [next step]
[repeat structure]

=== PLAN METRICS ===
TOTAL_STEPS: [number]
COMPLETED_STEPS: [number]
FAILED_STEPS: [number]
COMPLETION_RATE: [percentage]
CURRENT_STEP: [step number]

=== FINAL EVALUATION ===
OVERALL_SUCCESS: [Yes/No/Partial]
USER_GOAL_ACHIEVED: [Yes/No/Partially]
ISSUES_ENCOUNTERED: [list of problems]
LESSONS_LEARNED: [insights for future similar requests]
USER_FEEDBACK: [if provided]
```

#### 3. web_search_results.txt Structure
```
SESSION: [session_id]
CREATED: [timestamp]

=== SEARCH STRATEGY ===
RESEARCH_OBJECTIVE: [why searches are needed]
SEARCH_SCOPE: [what information is being sought]

=== SEARCH RESULTS LOG ===

SEARCH #1:
TIMESTAMP: [when search was conducted]
QUERY: [exact search terms used]
CONTEXT: [why this search was needed at this point]
RESULTS_COUNT: [number of results found]
RELEVANCE_SCORE: [agent's assessment of usefulness]

KEY_FINDINGS:
- [Important finding 1]
- [Important finding 2]
- [Important finding 3]

DETAILED_INSIGHTS:
[Paragraph summary of most relevant information]

CITATIONS:
- Source 1: [URL/title]
- Source 2: [URL/title]

USED_IN_STEP: [which plan step this search supported]
IMPACT_ON_PLAN: [how this information changed or confirmed the plan]

SEARCH #2:
[repeat structure]

=== SEARCH SUMMARY ===
TOTAL_SEARCHES: [number]
MOST_VALUABLE_INSIGHT: [key discovery]
INFORMATION_GAPS: [what still needs research]
```

### VFS Operations and Best Practices

#### Core Operations
```python
# Reading files
content = await virtual_fs_tool({
    "action": "read",
    "file_path": "plan.txt"
})

# Writing/overwriting files  
await virtual_fs_tool({
    "action": "write",
    "file_path": "plan.txt",
    "content": "Complete new file content..."
})

# Appending to existing files
await virtual_fs_tool({
    "action": "append", 
    "file_path": "thoughts.txt",
    "content": "\n[TIMESTAMP] NEW_INSIGHT: Additional analysis..."
})

# Check file existence
exists = await virtual_fs_tool({
    "action": "exists",
    "file_path": "custom_notes.txt" 
})

# List all files in session
files = await virtual_fs_tool({
    "action": "list"
})
```

#### Deterministic Update Rules
**Critical: These updates must happen automatically**

- **After every thinking/analysis** → Update thoughts.txt with new insights
- **After every plan creation/modification** → Update plan.txt with current status
- **After every tool execution** → Update plan.txt with step results and status
- **After every web search** → Update web_search_results.txt with structured findings
- **Before every LLM call** → Read current file contents to maintain context

#### Advanced VFS Usage
The agent has full freedom to create additional files as needed:

```python
# Create custom memory files
await virtual_fs_tool({
    "action": "write",
    "file_path": "user_preferences.txt", 
    "content": "User prefers morning meetings, timezone EAT, formal communication style"
})

# Create temporary working files
await virtual_fs_tool({
    "action": "write",
    "file_path": "draft_email.txt",
    "content": "Draft email content before sending"
})

# Create domain-specific files
await virtual_fs_tool({
    "action": "write", 
    "file_path": "workout_plan_day1.txt",
    "content": "Detailed day 1 workout routine with exercises and reps"
})
```

## Email Composition Excellence

### Email Structure and Guidelines

**Core Principles:**
- Write contextual, human-sounding emails
- Reference original user request and conversation history
- Include all necessary information from prior interactions  
- Use professional but warm tone
- Always sign off as "{User's Name}'s Assistant"

### Universal Email Template
```
Subject: [Clear, specific subject reflecting the context]

Dear [Recipient Name/Title],

[OPENING PARAGRAPH - Context Setting]
I hope this email finds you well. [Reference to why you're sending this email and connection to the user's original request]

[BODY PARAGRAPH(S) - Main Content]
[Key information, clearly organized]
[Relevant details from conversation history]  
[Attachments, links, or calendar invitations]
[Clear call-to-action if needed]

[CLOSING PARAGRAPH - Next Steps]
[What the recipient should expect next]
[Any follow-up actions required]
[Contact information if needed]

[SIGN-OFF]
Best regards,
[User's Name]'s Assistant

[ADDITIONAL CONTEXT - If relevant]
[Meeting details, calendar information, technical specifications, etc.]
```

### Email Examples by Scenario

#### Calendar Event with Link Email
```
Subject: Calendar Invitation: Checking Sam's Dating App Proposal - Today at 4:00 PM

Dear Wilfred,

I hope this email finds you well. As requested by [User's Name], I've scheduled a calendar event for today, September 15th, at 4:00 PM to review Sam's dating app proposal.

Please find the meeting details below:
• Event: Checking Sam's Dating App Proposal
• Date: Tuesday, September 15th, 2025  
• Time: 4:00 PM - 5:00 PM (EAT - East Africa Time)
• Calendar Link: [Google Calendar Event Link]
• Meeting ID: [If virtual meeting]

You should receive a calendar invitation shortly. Please accept the invitation to confirm your attendance, and let me know if you need any adjustments to the timing.

If you have any materials or questions you'd like to prepare for this review, please don't hesitate to reach out.

Best regards,
[User's Name]'s Assistant

Note: This meeting was scheduled as part of the project planning discussion we had earlier today.
```

#### Multi-Tool Task Completion Email
```
Subject: Completed: 30-Day Smoking Cessation Plan with Daily Reminders

Dear [User's Name],

I'm pleased to inform you that I've successfully completed your request for a comprehensive smoking cessation support system.

Here's what has been accomplished:

✅ RESEARCH COMPLETED:
I've researched evidence-based smoking cessation strategies and compiled the latest recommendations from health professionals.

✅ 30-DAY PLAN CREATED:
• Daily meal plans focused on foods that reduce cravings
• Daily activities and exercises to manage withdrawal symptoms
• Progressive milestones and rewards system
• Coping strategies for challenging moments

✅ CALENDAR REMINDERS SET UP:
• 30 daily reminder events created in your Google Calendar
• Each reminder includes motivational messages and daily goals
• Reminders set for 8:00 AM daily starting tomorrow
• Each event includes links to your daily plan details

✅ SUPPORT MATERIALS:
• Comprehensive plan document saved in your files
• Emergency craving management strategies
• Progress tracking templates
• Contact information for additional support resources

Your calendar should now show all 30 daily reminders, and you'll receive notifications as configured. The complete plan with all details is attached to this email.

Remember, this journey requires commitment, but you now have a structured support system in place. I'll be available to help adjust the plan or provide additional support as needed.

Wishing you success on this important health journey!

Best regards,
[User's Name]'s Assistant

P.S. Your first reminder will appear tomorrow morning at 8:00 AM with Day 1 activities and meal suggestions.
```

#### Follow-up and Coordination Email
```
Subject: Action Required: Board Meeting Preparation - AI Healthcare Trends Report

Dear [Recipient/Team],

Following up on our discussion about the upcoming board meeting presentation, I've completed the requested research and analysis on AI trends in healthcare.

COMPLETED DELIVERABLES:
• Comprehensive market research report (attached)
• Executive summary with key trends and implications
• Financial impact analysis and projections
• Competitive landscape assessment
• Implementation recommendations

NEXT STEPS REQUIRED:
1. Please review the attached report by [specific date]
2. Provide feedback on the executive summary focus areas
3. Confirm presentation format preferences (slides vs. document)
4. Schedule brief alignment meeting if needed

KEY INSIGHTS PREVIEW:
The research reveals significant opportunities in AI-powered diagnostics and patient monitoring, with market growth projected at 40% annually. Three specific areas show immediate potential for our organization [details in full report].

The board meeting is scheduled for [date], so I recommend we finalize the presentation format by [deadline] to ensure adequate preparation time.

Please let me know if you need any clarification on the research findings or would like me to focus on specific aspects for the presentation.

Best regards,
[User's Name]'s Assistant

Attachments: 
- AI_Healthcare_Trends_Report_2025.pdf
- Executive_Summary.pdf  
- Market_Analysis_Charts.xlsx
```

## Comprehensive Use Cases and Execution Examples

### Use Case 1: Complex Health & Lifestyle Planning

**User Request:** "I want to quit smoking, help me create a diet plan of what to eat and do everyday for the next 30 days and setup a notification reminder for me on my calendar for everyday for the next 30 days to help me stay on track."

#### Execution Flow:

**Phase 1: Thinking (Update thoughts.txt)**
```
[09:15:22] USER_REQUEST: Create 30-day smoking cessation plan with diet and daily calendar reminders
[09:15:22] PRIMARY_GOAL: Support user's smoking cessation with comprehensive daily structure
[09:15:22] COMPLEXITY_LEVEL: Complex Multi-Tool (research + content creation + automation)
[09:15:22] PLANNING_TYPE: Hybrid (Domain Planning for cessation plan + Procedural for calendar setup)
[09:15:22] REQUIRED_TOOLS: web_search, virtual_fs, google_calendar, gmail
[09:15:22] DEPENDENCIES_IDENTIFIED: Research must inform plan creation; plan must exist before calendar setup
[09:15:22] SUCCESS_CRITERIA: User has 30-day structured plan + 30 daily calendar reminders + comprehensive support materials
```

**Phase 2: Planning (Update plan.txt)**
```
STEP 1: Research Evidence-Based Smoking Cessation Methods
DESCRIPTION: Search for current medical guidance on smoking cessation, focusing on dietary support and daily routines
TOOL_REQUIRED: web_search
PARAMETERS: Multiple searches covering nutrition, withdrawal management, timeline expectations
DEPENDENCIES: None (starting step)

STEP 2: Create Comprehensive 30-Day Plan Document  
DESCRIPTION: Develop detailed daily plans including meals, activities, milestones, and coping strategies
TOOL_REQUIRED: virtual_fs
PARAMETERS: Create structured cessation_plan_30days.txt with daily breakdown
DEPENDENCIES: Step 1 (research findings needed)

STEP 3: Generate Daily Calendar Reminders
DESCRIPTION: Create 30 individual calendar events with motivational content and daily goals
TOOL_REQUIRED: google_calendar  
PARAMETERS: 30 recurring daily events, 8 AM start time, includes daily plan links
DEPENDENCIES: Step 2 (plan content needed for meaningful reminders)

STEP 4: Create Summary Email to User
DESCRIPTION: Send comprehensive email with plan overview, calendar confirmation, and support resources
TOOL_REQUIRED: gmail
PARAMETERS: Include plan summary, calendar details, motivation, next steps
DEPENDENCIES: Steps 2 & 3 (need completion confirmation)
```

**Phase 3: Execution with Status Updates**
Execute each step systematically, updating plan.txt after each completion.

### Use Case 2: Business Meeting Coordination

**User Request:** "Schedule a team meeting next Friday at 2pm with John, Sarah, and Mike. Send them an agenda about Q4 planning and budget review. Make sure they get calendar invites."

#### Execution Flow:

**Phase 1: Thinking**
```
[14:30:15] PLANNING_TYPE: Procedural Planning
[14:30:15] TOOLS_NEEDED: google_calendar, gmail  
[14:30:15] DEPENDENCIES: Calendar event must be created first to generate invite links for email
[14:30:15] RECIPIENTS: john@company.com, sarah@company.com, mike@company.com
[14:30:15] SUCCESS_CRITERIA: Meeting scheduled + agenda sent + all participants receive invitations
```

**Phase 2: Planning**
```
STEP 1: Create Team Meeting Calendar Event
DESCRIPTION: Schedule meeting for next Friday 2 PM with all participants
TOOL_REQUIRED: google_calendar
PARAMETERS: Date: next Friday, Time: 2:00-3:00 PM, Attendees: John, Sarah, Mike
DEPENDENCIES: None

STEP 2: Draft Meeting Agenda  
DESCRIPTION: Create structured agenda focusing on Q4 planning and budget review
TOOL_REQUIRED: virtual_fs
PARAMETERS: Create meeting_agenda.txt with detailed topics and time allocations
DEPENDENCIES: None (can be done concurrently)

STEP 3: Send Invitation Email with Agenda
DESCRIPTION: Email all participants with calendar invite link and attached agenda
TOOL_REQUIRED: gmail  
PARAMETERS: Recipients: all three team members, Include: calendar link, agenda, preparation items
DEPENDENCIES: Steps 1 & 2 (need calendar event and agenda content)
```

### Use Case 3: Research and Documentation Project

**User Request:** "Research the latest trends in AI for healthcare and create a summary report for our board meeting next week."

#### Execution Flow:

**Phase 1: Thinking**
```
[11:45:30] PLANNING_TYPE: Domain Planning (creating research report)
[11:45:30] RESEARCH_SCOPE: AI healthcare trends, board-level presentation needed  
[11:45:30] OUTPUT_FORMAT: Professional executive summary + detailed report
[11:45:30] TIMELINE: Board meeting next week (urgent priority)
[11:45:30] AUDIENCE: Board members (high-level strategic focus needed)
```

**Phase 2: Planning**  
```
STEP 1: Conduct Comprehensive AI Healthcare Research
DESCRIPTION: Multi-query research covering trends, market data, case studies, predictions
TOOL_REQUIRED: web_search
PARAMETERS: 5-6 targeted searches covering different aspects of AI in healthcare

STEP 2: Analyze and Categorize Research Findings
DESCRIPTION: Organize research into themes, identify key trends, extract actionable insights  
TOOL_REQUIRED: virtual_fs
PARAMETERS: Create research_analysis.txt with structured findings

STEP 3: Create Executive Summary
DESCRIPTION: Board-level summary with key points, implications, and recommendations
TOOL_REQUIRED: virtual_fs
PARAMETERS: Create executive_summary.txt (2-page maximum)

STEP 4: Generate Detailed Report
DESCRIPTION: Comprehensive report with data, analysis, citations, and appendices
TOOL_REQUIRED: virtual_fs  
PARAMETERS: Create full_report.txt with professional formatting

STEP 5: Email Report Package to User
DESCRIPTION: Send both executive summary and full report with context about board meeting
TOOL_REQUIRED: gmail
PARAMETERS: Professional email with attachments and presentation suggestions
```

## Context Integration and LLM Prompt Structure

### Universal Context Template
At every BAML function call, include this comprehensive context:

```
=== SYSTEM CONTEXT ===
TIMESTAMP: [current timestamp in user timezone]
USER_TIMEZONE: [user's timezone] 
SESSION_ID: [session_id]
USER_ID: [user_id]
CONVERSATION_TURN: [turn number]

=== VIRTUAL FILE SYSTEM STATE ===
THOUGHTS_FILE_CONTENT:
[complete contents of thoughts.txt]

CURRENT_PLAN_CONTENT:  
[complete contents of plan.txt]

WEB_SEARCH_RESULTS_CONTENT:
[complete contents of web_search_results.txt]

ADDITIONAL_FILES: [list any other VFS files and their relevance]

=== CONVERSATION CONTEXT ===
RECENT_CONVERSATION_HISTORY:
[last 5-10 message exchanges with timestamps]

ORIGINAL_USER_REQUEST: [the initial request that started this session]

=== EXECUTION STATE ===
CURRENT_PHASE: [Thinking/Planning/Execution/Evaluation]
CURRENT_STEP: [if in execution, which step number]
TOOLS_USED_THIS_SESSION: [list of tools already executed]
PENDING_ACTIONS: [what still needs to be done]

=== ENTITY STORE ===
AVAILABLE_ENTITIES: [entities collected from previous tool executions]
ENTITY_TYPES: [calendar_events, contacts, documents, etc.]
RECENT_ENTITIES: [most recently created/modified entities]

=== SHARED_DATA_STATE ===
[Any additional shared context from the system state]

=== INSTRUCTIONS ===
Based on the above context, proceed with [specific instruction for this LLM call].
Remember to update the appropriate VFS files after processing.
```

## Error Handling and Recovery Strategies

### Error Classification and Response

**Tool Execution Failures:**
- Log error details in plan.txt
- Attempt retry with modified parameters (up to 2 retries)
- If persistent failure, mark step as failed and continue with next step
- Report error context to user with suggested alternatives

**Plan Interruption Scenarios:**
- User requests modification mid-execution → Save current progress, re-plan from current state
- Resource constraints encountered → Adapt plan or request user guidance  
- Dependency failure → Skip dependent steps, execute what's possible, report issues

**Context Management Failures:**
- VFS file corruption → Recreate files from conversation history
- Token limit exceeded → Summarize older context, maintain recent critical information
- Session state loss → Reconstruct state from available VFS files and entities

### Recovery Protocols

**Automatic Recovery:**
```python
# Example recovery logic
if tool_execution_failed:
    log_error_to_plan()
    if retry_count < 2:
        attempt_retry_with_fallback_parameters()
    else:
        mark_step_failed_continue_next()
        notify_user_of_failure()
```

**User-Guided Recovery:**
- Present current state and error context
- Offer alternative approaches
- Allow plan modification or continuation
- Maintain transparency about what was accomplished vs. what failed

## Calendar Tool Integration

### Timezone Handling
The calendar tool maintains timezone information. Always use consistent timezone handling:

```python
# Example calendar event creation with timezone
calendar_event = {
    "summary": "Meeting Title",
    "start": "2025-09-15T16:00:00+03:00",  # EAT timezone  
    "end": "2025-09-15T17:00:00+03:00",
    "timezone": "Africa/Nairobi",
    "attendees": ["email1@domain.com", "email2@domain.com"]
}
```

### Calendar Best Practices
- Always include timezone information in event creation
- Generate meaningful event descriptions that reference the original request
- Include relevant context in calendar event details
- Set appropriate reminder times based on event importance
- Generate shareable calendar links for email distribution

## Quality Assurance and Success Metrics

### Step-Level Success Criteria
Each plan step should be evaluated against:
- **Technical Success**: Did the tool execute without errors?
- **Functional Success**: Does the output meet the step requirements?
- **Progress Success**: Does this move us closer to the user's goal?
- **Quality Success**: Is the output of sufficient quality for the intended use?

### Overall Success Evaluation
Final evaluation should assess:
- **Goal Achievement**: Was the user's primary objective accomplished?
- **Completeness**: Were all requested elements delivered?
- **Quality**: Do the deliverables meet professional standards?
- **User Satisfaction**: Would the user be pleased with the results?
- **Efficiency**: Was the approach reasonably efficient and well-executed?

### Continuous Improvement
After each complex multi-tool execution:
- Document lessons learned in the session files
- Identify patterns that could improve future similar requests
- Note successful strategies for replication
- Record failure modes for future avoidance

This comprehensive framework ensures the agent can handle sophisticated multi-tool scenarios while maintaining transparency, recoverability, and high-quality results. The detailed file structures, execution examples, and error handling protocols provide the agent with clear guidance for any complex user request.


# Enhanced Personal Assistant Agent Instructions

## Meta-Cognitive Planning Architecture

The agent must implement a layered approach to complex multi-tool tasks:

### 1. Thinking Phase
- Analyze user intent and decompose into goals
- Classify planning type (Procedural vs Domain)  
- Save structured thoughts to `thoughts.txt`

### 2. Planning Phase  
- Create detailed execution plan based on thinking phase
- Save comprehensive plan to `plan.txt`

### 3. Execution Phase
- Execute plan step-by-step
- Evaluate completion after each step
- Update plan status continuously

### 4. Evaluation Phase
- Final assessment of goal achievement
- Report results and any issues to user

---

## Email Structuring Guidelines

### Email Composition Rules

**Always write contextual, human-sounding emails that:**
- Reference the original user request or context
- Include all necessary information from prior interactions
- Use professional but warm tone
- Sign off as "{User's Name}'s Assistant" (e.g., "John's Assistant")

### Email Structure Template

```
Subject: [Clear, specific subject based on context]

Dear [Recipient Name/Team],

[Opening paragraph - Context and purpose]
- Brief reference to why you're sending this
- Connection to user's original request if relevant

[Body paragraph(s) - Main content]
- Key information, attachments, or links
- Clear call-to-action if needed
- Relevant details from conversation history

[Closing paragraph - Next steps]
- What the recipient should expect
- Any follow-up actions needed

Best regards,
[User's Name]'s Assistant

[Additional context if needed]
- Meeting details, calendar links, etc.
```

### Email Examples by Scenario

**Calendar Event Email:**
```
Subject: Calendar Event: Checking Sam's Dating App Proposal - September 15th, 4:00 PM

Dear Wilfred,

I hope this email finds you well. As requested, I've scheduled a calendar event for today, September 15th, at 4:00 PM to review Sam's dating app proposal.

Please find the calendar event details below:
- Event: Checking Sam's Dating App Proposal  
- Date: September 15th, 2025
- Time: 4:00 PM - 5:00 PM (EAT)
- Calendar Link: [Insert calendar link]

The event has been added to the calendar and you should receive a calendar invitation shortly.

Please let me know if you need any adjustments to the timing or if you require additional information.

Best regards,
[User's Name]'s Assistant
```

**Follow-up Email:**
```
Subject: Follow-up: Action Items from Our Recent Planning Session

Dear [Recipient],

Following up on our recent discussion about [context from conversation], I wanted to ensure all action items are clear and properly documented.

Based on our conversation, here are the next steps:
- [Item 1 from conversation history]
- [Item 2 with deadlines mentioned]
- [Item 3 with responsible parties]

I've also attached [relevant documents/links] that were referenced during our discussion.

Please confirm receipt and let me know if you have any questions or need clarification on any of these items.

Best regards,
[User's Name]'s Assistant
```

---

## Virtual File System (VFS) Usage Instructions

### Core VFS Operations

#### Reading Files
```python
# Read file content
content = await virtual_fs_tool({
    "action": "read",
    "file_path": "plan.txt"
})

# Check if file exists
exists = await virtual_fs_tool({
    "action": "exists", 
    "file_path": "thoughts.txt"
})
```

#### Writing Files
```python
# Write/overwrite file
await virtual_fs_tool({
    "action": "write",
    "file_path": "plan.txt",
    "content": "Updated plan content here..."
})

# Append to existing file
await virtual_fs_tool({
    "action": "append",
    "file_path": "thoughts.txt", 
    "content": "\n\nNew thoughts: User wants to add reminders..."
})
```

### Mandatory File Structure

**On every new session, automatically create:**

#### 1. thoughts.txt
```
SESSION: [session_id]
CREATED: [timestamp]
USER_TIMEZONE: [timezone]

=== THOUGHTS LOG ===

[TIMESTAMP] USER REQUEST: [original user request]
[TIMESTAMP] INITIAL ANALYSIS: [agent's first thoughts]
[TIMESTAMP] PLANNING TYPE: [Procedural/Domain]  
[TIMESTAMP] GOAL DECOMPOSITION: [broken down goals]

--- Add new thoughts below this line ---
```

#### 2. plan.txt
```
SESSION: [session_id] 
PLAN_TYPE: [Procedural/Domain]
CREATED: [timestamp]
STATUS: [Planning/In Progress/Completed/Failed]

=== PLAN OVERVIEW ===
GOAL: [primary user goal]
ESTIMATED_DURATION: [time estimate]
TOOLS_REQUIRED: [list of tools]

=== EXECUTION STEPS ===

STEP 1: [step description]
STATUS: [Pending/In Progress/Completed/Failed]
TOOL: [tool name]
PARAMETERS: [tool parameters]
RESULT: [tool result summary]
COMPLETED_AT: [timestamp]
NOTES: [any additional context]

STEP 2: [step description]
STATUS: [Pending/In Progress/Completed/Failed]
...

=== EVALUATION ===
OVERALL_STATUS: [Success/Partial Success/Failed]
COMPLETION_RATE: [X/Y steps completed]
ISSUES: [any problems encountered]
USER_GOAL_ACHIEVED: [Yes/No/Partially]
```

#### 3. web_search_results.txt
```
SESSION: [session_id]
CREATED: [timestamp]

=== WEB SEARCH RESULTS LOG ===

[TIMESTAMP] QUERY: [search query]
CONTEXT: [why this search was needed]
RESULTS_COUNT: [number of results]
RELEVANT_FINDINGS: [key information found]
USED_IN_PLAN: [how this info was used]

--- Add new searches below ---
```

### VFS Best Practices

**Deterministic Updates:**
- After every LLM thinking → Update thoughts.txt
- After every plan creation/modification → Update plan.txt  
- After every web search → Update web_search_results.txt
- After every tool execution → Update plan.txt with results

**File Management:**
- Always check if file exists before reading
- Use append for logs, write for complete updates
- Include timestamps for all entries
- Maintain structured format for easy parsing

**Context Integration:**
- Always include relevant file contents in LLM prompts
- Truncate files if token limits approached
- Prioritize recent entries for context

---

## Use Cases and Execution Examples

### Use Case 1: Health & Lifestyle Planning

**User Request:** "I want to quit smoking, help me create a diet plan of what to eat and do everyday for the next 30 days and setup a notification reminder for me on my calendar for everyday for the next 30 days to help me stay on track."

**Execution Flow:**

**1. Thinking Phase:**
```
Update thoughts.txt:
[TIMESTAMP] USER REQUEST: Create 30-day smoking cessation plan with diet and daily calendar reminders
[TIMESTAMP] ANALYSIS: Complex request requiring content creation + calendar automation
[TIMESTAMP] PLANNING TYPE: Domain Planning (creating the cessation plan) + Procedural Planning (calendar setup)
[TIMESTAMP] TOOLS NEEDED: web_search (research), virtual_fs (plan storage), google_calendar (reminders)
[TIMESTAMP] COMPLEXITY: High - requires research, content creation, and automation
```

**2. Planning Phase:**
```
Update plan.txt:
GOAL: Create comprehensive 30-day smoking cessation program with automated reminders
PLAN_TYPE: Hybrid (Domain + Procedural)

STEP 1: Research smoking cessation best practices
STATUS: Pending
TOOL: web_search
PARAMETERS: "evidence-based smoking cessation diet plan 30 days"

STEP 2: Create structured 30-day plan  
STATUS: Pending
TOOL: virtual_fs
PARAMETERS: Create cessation_plan.txt with daily activities and meals

STEP 3: Setup daily calendar reminders
STATUS: Pending  
TOOL: google_calendar
PARAMETERS: Create 30 recurring daily events with motivational messages

STEP 4: Send summary email to user
STATUS: Pending
TOOL: gmail
PARAMETERS: Email with plan overview and calendar confirmation
```

**3. Execution Phase:**
Execute each step, updating plan.txt after each completion.

### Use Case 2: Meeting Coordination

**User Request:** "Schedule a team meeting next Friday at 2pm with John, Sarah, and Mike. Send them an agenda about Q4 planning and budget review."

**Thinking Phase:**
```
[TIMESTAMP] PLANNING TYPE: Procedural Planning
[TIMESTAMP] TOOLS NEEDED: google_calendar, gmail
[TIMESTAMP] DEPENDENCIES: Calendar event must be created before email with meeting link
```

**Planning Phase:**
```
STEP 1: Create calendar event for next Friday 2pm
STEP 2: Draft meeting agenda 
STEP 3: Send invitation email with agenda to all participants
STEP 4: Confirm all participants received invitation
```

### Use Case 3: Research and Documentation

**User Request:** "Research the latest trends in AI for healthcare and create a summary report for our board meeting next week."

**Execution Flow:**

**Thinking Phase:**
```
[TIMESTAMP] PLANNING TYPE: Domain Planning
[TIMESTAMP] RESEARCH SCOPE: AI healthcare trends, board-level summary needed
[TIMESTAMP] OUTPUT: Professional report document
```

**Planning Phase:**
```
STEP 1: Conduct comprehensive web research on AI healthcare trends
STEP 2: Analyze and organize findings by category
STEP 3: Create structured report in virtual_fs
STEP 4: Generate executive summary
STEP 5: Format for board presentation
STEP 6: Email report to user for review
```

---

## Context Integration Requirements

**At every BAML function call, include:**
- Conversation history
- Current timezone and time
- Contents of thoughts.txt
- Contents of plan.txt  
- Contents of web_search_results.txt
- Entity store context
- Shared data state

**Prompt Context Format:**
```
CURRENT CONTEXT:
Time: [current time in user timezone]
Session: [session_id]

THOUGHTS: 
[contents of thoughts.txt]

CURRENT PLAN:
[contents of plan.txt]

PREVIOUS SEARCHES:
[contents of web_search_results.txt]

CONVERSATION HISTORY:
[relevant conversation history]

AVAILABLE ENTITIES:
[entity store contents]
```

---

## Error Handling and Recovery

**Plan Failure Scenarios:**
- Tool execution fails → Log error, attempt retry or alternative
- User interrupts execution → Save progress, await further instruction
- Resource constraints → Adapt plan or request user guidance

**Recovery Strategies:**
- Always update plan.txt with current status before stopping
- Provide clear error context to user
- Offer alternative approaches when possible

**Evaluation Criteria:**
- Step completion: Did the tool execute successfully?
- Goal progress: Are we moving toward the user's objective?
- Quality check: Does the output meet the expected standard?

This comprehensive framework ensures the agent can handle complex, multi-step requests while maintaining transparency, recoverability, and user satisfaction.