// Enhanced Intent-Driven Personal Assistant BAML Functions
// Redesigned for robust classification, comprehensive planning, and efficient execution

// ============================================================================
// INTENT CLASSIFICATION - ENHANCED
// ============================================================================

class IntentClassification {
  complexity_level string  // "simple", "comprehensive"
  task_category string     // "greeting", "question", "research", "planning", "creation", "analysis"
  user_intent string       // Clear description of what user wants
  requires_tools bool      // Whether any tools are needed
  estimated_steps int      // Estimated number of execution steps (1-12)
  reasoning string         // Why this classification was chosen
}

function ClassifyUserIntent(
  user_message: string,
  available_tools: string,
  conversation_context: string?
) -> IntentClassification {
  client AgenticGeminiRateLimited
  prompt #"
    You are Claude's intent classification system. Your role is to deeply understand user requests and classify them for optimal execution. This classification directly impacts the user's experience quality.

    AVAILABLE TOOLS:
    {{ available_tools }}

    CONVERSATION CONTEXT:
    {{ conversation_context }}

    USER MESSAGE TO CLASSIFY:
    {{ user_message }}

    CORE CLASSIFICATION FRAMEWORK:

    **SIMPLE** - Direct, self-contained tasks requiring minimal cognitive load:
    • Characteristics: Immediate answers, single-step actions, basic interactions
    • Cognitive markers: "What is", "How do I", "Can you", basic greetings
    • Tool usage: 0-1 tools, no interdependencies
    • Time scope: Immediate (1-5 minutes)
    • Examples: "Hello", "What time is it?", "Define quantum computing", "Write a haiku about coffee"
    • Step range: 1-4 steps

    **COMPREHENSIVE** - Multi-faceted tasks requiring synthesis, analysis, or complex execution:
    • Characteristics: Multiple information sources, decision-making, deliverable creation
    • Cognitive markers: "Research and analyze", "Create a plan", "Compare options", "Find the best"
    • Tool usage: 2+ tools with potential interdependencies
    • Time scope: Extended (5-45 minutes)
    • Examples: "Research market trends for EVs and create investment recommendations", "Plan a 2-week Europe trip under $3000", "Analyze my business idea and create an action plan"
    • Step range: 5-12 steps

    ADVANCED CLASSIFICATION SIGNALS:

    **Complexity Escalators** (push toward COMPREHENSIVE):
    - Multiple subjects or domains mentioned
    - Words like "best", "compare", "analyze", "comprehensive", "detailed", "thorough"
    - Conditional requirements ("if X, then Y")
    - Deliverable creation beyond simple text
    - Time-sensitive research requiring current information
    - Multi-step processes implied
    - Business/professional context requiring depth

    **Simplicity Anchors** (keep as SIMPLE):
    - Single, direct questions with clear answers
    - Basic definitions or explanations
    - Social interactions (greetings, thanks)
    - Simple creative requests (single poem, joke)
    - Fact-checking single claims
    - Basic how-to instructions for common tasks

    **Context Considerations**:
    - Previous conversation may indicate ongoing complex project
    - User expertise level affects task complexity
    - Available tools determine execution possibilities
    - Time constraints mentioned by user

    TASK CATEGORIES (refined):
    - **greeting**: Social interactions, conversation starters, acknowledgments
    - **question**: Information requests, fact-checking, explanations
    - **research**: Information gathering requiring multiple sources or current data
    - **planning**: Strategy creation, organizing, scheduling, decision frameworks
    - **creation**: Content generation, building, designing (beyond simple text)
    - **analysis**: Data examination, comparison, evaluation, synthesis

    STEP ESTIMATION METHODOLOGY:
    Consider the full execution path:
    1. Information gathering steps (research, data collection)
    2. Processing steps (analysis, synthesis, planning)
    3. Creation steps (writing, formatting, organizing)
    4. Validation steps (checking, refining)
    5. Delivery steps (presenting, explaining)

    CLASSIFICATION DECISION TREE:
    1. Is this a greeting or basic social interaction? → SIMPLE (greeting)
    2. Is this a single, factual question with a direct answer? → SIMPLE (question)
    3. Does this require current information from multiple sources? → COMPREHENSIVE (research)
    4. Does this involve creating something beyond a simple response? → Check complexity
    5. Are there multiple components or requirements? → COMPREHENSIVE
    6. Does this require professional-level output? → COMPREHENSIVE
    7. Default: Consider cognitive load and tool requirements

    CRITICAL: Avoid the "focused trap" - resist defaulting to a middle complexity. Most tasks are either clearly simple (direct answers) or genuinely comprehensive (multi-step with depth).

    REQUIRED OUTPUT FORMAT:
    {
      "complexity_level": "simple" | "comprehensive",
      "task_category": "greeting" | "question" | "research" | "planning" | "creation" | "analysis",
      "user_intent": "Precise description of user's goal",
      "requires_tools": true | false,
      "estimated_steps": 1-12,
      "reasoning": "Detailed explanation of classification decision including key factors considered"
    }

    Examples:

    User: "Hi there, what can you help me with?"
    {
      "complexity_level": "simple",
      "task_category": "greeting",
      "user_intent": "User is greeting and asking about capabilities",
      "requires_tools": false,
      "estimated_steps": 1,
      "reasoning": "Basic greeting with capability inquiry - no tools needed, immediate response, social interaction category"
    }

    User: "What's the capital of France?"
    {
      "complexity_level": "simple",
      "task_category": "question",
      "user_intent": "User wants to know the capital city of France",
      "requires_tools": false,
      "estimated_steps": 1,
      "reasoning": "Direct factual question with single, well-known answer - no research needed"
    }

    User: "Research the best electric vehicles under $40k and create a comparison table with pros and cons"
    {
      "complexity_level": "comprehensive",
      "task_category": "research",
      "user_intent": "User wants comprehensive EV research with structured comparison deliverable",
      "requires_tools": true,
      "estimated_steps": 8,
      "reasoning": "Multiple complexity escalators: 'best' requires evaluation, 'research' needs current data, 'comparison table' is structured deliverable, price constraint adds filtering requirement. Steps: search EVs, gather specs/reviews, filter by price, analyze pros/cons, create table, format output."
    }
    "#
}

// ============================================================================
// STRUCTURED PLANNING - ENHANCED
// ============================================================================

class TodoItem {
  id string
  title string
  description string
  tool_required string?
  tool_parameters map<string, string>?
  estimated_minutes int
  dependencies string[]
  status string
}

class StructuredPlan {
  plan_summary string
  total_estimated_minutes int
  todos TodoItem[]
  success_criteria string
  workspace_files string[]
}

function CreateStructuredPlan(
  user_intent: string,
  complexity_level: string,
  task_category: string,
  available_tools: string,
  estimated_steps: int
) -> StructuredPlan {
  client AgenticGeminiRateLimited
  prompt #"
    You are Claude's strategic planning system. Your role is to create execution-ready plans that maximize success probability while maintaining efficiency. Every plan you create directly impacts user satisfaction and task completion quality.

    PLANNING CONTEXT:
    User Intent: {{ user_intent }}
    Complexity Level: {{ complexity_level }}
    Task Category: {{ task_category }}
    Available Tools: {{ available_tools }}
    Estimated Steps: {{ estimated_steps }}

    PLANNING PHILOSOPHY:
    1. **Outcome-Driven**: Every todo must advance toward the user's ultimate goal
    2. **Tool-Aware**: Plan only what can be executed with available tools
    3. **Fault-Tolerant**: Build in validation and error-handling where needed
    4. **User-Centric**: Optimize for user value, not system convenience
    5. **Adaptive**: Allow for iterative refinement during execution

    COMPLEXITY-SPECIFIC PLANNING STRATEGIES:

    **SIMPLE PLANS** (1-4 todos, 1-5 minutes):
    Core principle: Direct path to answer with minimal overhead
    
    Structure patterns:
    - Single Response: [Analyze request → Provide answer]
    - Quick Creation: [Understand requirements → Create content]
    - Basic Lookup: [Process query → Return information]
    
    
    Characteristics:
    - Minimal workspace usage (only if user needs to save something)
    - Direct execution without intermediate steps
    - Focus on immediate value delivery
    - No complex tool chaining

    **COMPREHENSIVE PLANS** (5-12 todos, 5-45 minutes):
    Core principle: Systematic approach ensuring thorough, high-quality outcomes
    
    Structure patterns:
    - Research & Analysis: [Define scope → Gather data → Analyze → Synthesize → Present]
    - Planning & Strategy: [Understand context → Research options → Evaluate → Create plan → Validate]
    - Creation & Synthesis: [Research → Plan structure → Create components → Integrate → Refine]
    
    Characteristics:
    - Strategic workspace usage for organization and deliverables
    - Multi-phase execution with checkpoints
    - Quality validation steps
    - Tool orchestration for complex workflows

    ADVANCED PLANNING PRINCIPLES:

    **Information Architecture**:
    - Start with information gathering if knowledge gaps exist
    - Structure research to build knowledge incrementally
    - Create decision points where multiple paths are possible
    - Plan for synthesis and integration of multiple information sources

    **Quality Assurance Integration**:
    - Build validation steps into comprehensive plans
    - Include refinement opportunities for high-stakes deliverables
    - Plan for edge case handling in research-heavy tasks

    **Workspace Strategy**:
    - Use workspace files as external memory for complex tasks
    - Create logical file organization that supports the workflow
    - Plan for intermediate artifacts that can be referenced later
    - Consider user's need to access or share workspace contents

    **Tool Orchestration Mastery**:
    Available tools and their strategic uses:
    - **tavily_search**: Current information, fact verification, market research
    - **virtual_fs**: Persistent storage, structured deliverables, interim results
    - **planning**: Meta-planning for especially complex multi-phase work
    - **system_prompt**: Context switching for specialized analysis modes

    **CRITICAL: Tool Parameter Requirements**:

    **virtual_fs tool parameters (EXACT FORMAT REQUIRED):**
    - Create file: action=create, filename=research_findings.md, content=file content here
    - Read file: action=read, filename=research_findings.md
    - Update file: action=update, filename=research_findings.md, content=updated content
    - Delete file: action=delete, filename=research_findings.md
    - List files: action=list

    **tavily_search tool parameters:**
    - Search: query=specific search terms here

    **planning tool parameters:**
    - Plan: task=task description, complexity=simple

    Tool chaining strategies:
    - Research → Workspace storage → Analysis → Deliverable creation
    - Multiple searches with iterative refinement
    - Workspace as central hub for complex information management

    EXECUTION READINESS CHECKLIST:
    - Each todo has clear, measurable completion criteria
    - Tool parameters are specific enough for reliable execution
    - Dependencies create logical workflow progression
    - Success criteria are observable and definitive
    - Time estimates reflect realistic execution complexity

    COMMON PITFALLS TO AVOID:
    - Over-planning simple tasks (keep simple plans truly simple)
    - Under-planning comprehensive tasks (don't skip crucial steps)
    - Creating dependencies that don't add value
    - Vague tool parameters that lead to execution failures
    - Success criteria that are subjective or unmeasurable
    - CRITICAL: Using wrong parameter names for virtual_fs (use "filename" not "file")
    - CRITICAL: Missing required "content" parameter for virtual_fs create/update actions
    - CRITICAL: Missing required "action" parameter for virtual_fs tool

    TOOL PARAMETER VALIDATION CHECKLIST:
    Before finalizing any todo with tool_required, verify:

    For virtual_fs tool:
    ✓ "action" parameter is present (create/read/update/delete/list)
    ✓ "filename" parameter is present for create/read/update/delete actions
    ✓ "content" parameter is present for create/update actions
    ✓ filename follows format: descriptive_name.md or research_findings.md

    For tavily_search tool:
    ✓ "query" parameter is present with specific search terms

    For planning tool:
    ✓ "task" parameter is present with task description
    ✓ "complexity" parameter is present (simple/medium/complex)

    REQUIRED OUTPUT FORMAT:
    {
      "plan_summary": "Clear description of the planned approach and expected outcome",
      "total_estimated_minutes": integer,
      "success_criteria": "Specific, measurable criteria for completion",
      "workspace_files": ["file1.md", "file2.md"],
      "todos": [
        {
          "id": "todo-1",
          "title": "Concise, action-oriented title",
          "description": "Detailed description with specific deliverables and quality expectations",
          "tool_required": "tool_name" | null,
          "tool_parameters": {"param": "value"} | null,
          "estimated_minutes": integer,
          "dependencies": [] | ["todo-id"],
          "status": "pending"
        }
      ]
    }

    EXAMPLE OUTPUTS:

    Simple Greeting Response:
    {
      "plan_summary": "Provide friendly greeting and capability overview",
      "total_estimated_minutes": 1,
      "success_criteria": "User receives welcoming response with clear understanding of available assistance",
      "workspace_files": [],
      "todos": [
        {
          "id": "todo-1",
          "title": "Welcome user and explain capabilities",
          "description": "Provide warm greeting and concise overview of how I can assist with various tasks",
          "tool_required": null,
          "tool_parameters": null,
          "estimated_minutes": 1,
          "dependencies": [],
          "status": "pending"
        }
      ]
    }

    Comprehensive EV Research:
    {
      "plan_summary": "Research electric vehicles under $40k, analyze features and value, create comparison deliverable",
      "total_estimated_minutes": 25,
      "success_criteria": "User receives comprehensive comparison table with at least 5 EVs, including key specs, pros/cons, and recommendations",
      "workspace_files": ["ev_research_data.md", "ev_comparison_table.md"],
      "todos": [
        {
          "id": "todo-1",
          "title": "Research current EV market under $40k",
          "description": "Search for available electric vehicles under $40,000, focusing on popular and well-reviewed models from major manufacturers",
          "tool_required": "tavily_search",
          "tool_parameters": {"query": "best electric vehicles under $40000 2024 2025"},
          "estimated_minutes": 5,
          "dependencies": [],
          "status": "pending"
        },
        {
          "id": "todo-2",
          "title": "Gather detailed specifications and reviews",
          "description": "Search for detailed specs, pricing, range, charging, and expert reviews for identified vehicles",
          "tool_required": "tavily_search",
          "tool_parameters": {"query": "EV specifications range charging reviews [model names from todo-1]"},
          "estimated_minutes": 6,
          "dependencies": ["todo-1"],
          "status": "pending"
        },
        {
          "id": "todo-3",
          "title": "Store research findings",
          "description": "Organize all gathered information into structured research file with vehicle profiles",
          "tool_required": "virtual_fs",
          "tool_parameters": {"action": "create", "filename": "ev_research_data.md", "content": "Research findings will be stored here"},
          "estimated_minutes": 4,
          "dependencies": ["todo-2"],
          "status": "pending"
        },
        {
          "id": "todo-4",
          "title": "Analyze pros and cons for each vehicle",
          "description": "Evaluate each vehicle's strengths and weaknesses considering factors like value, performance, reliability, features",
          "tool_required": null,
          "tool_parameters": null,
          "estimated_minutes": 5,
          "dependencies": ["todo-3"],
          "status": "pending"
        },
        {
          "id": "todo-5",
          "title": "Create comparison table deliverable",
          "description": "Build comprehensive comparison table with key specs, pros/cons, and ranking/recommendations",
          "tool_required": "virtual_fs",
          "tool_parameters": {"action": "create", "filename": "ev_comparison_table.md", "content": "Comparison table will be created here"},
          "estimated_minutes": 5,
          "dependencies": ["todo-4"],
          "status": "pending"
        }
      ]
    }
    "#
}

// ============================================================================
// PLAN EXECUTION - ENHANCED
// ============================================================================

class ExecutionResult {
  todo_completed bool
  next_todo_id string?
  workspace_updates string[]
  execution_summary string
  plan_complete bool
  final_output string?
}

function ExecutePlanStep(
  current_todo: string,
  plan_context: string,
  tool_results: string,
  workspace_state: string
) -> ExecutionResult {
  client AgenticGeminiRateLimited
  prompt #"
    You are Claude's execution evaluation system. Your role is to assess task completion quality and orchestrate efficient plan progression. Your decisions directly impact user satisfaction and plan success rates.

    EXECUTION CONTEXT:
    Current Todo: {{ current_todo }}
    Overall Plan: {{ plan_context }}
    Tool Results: {{ tool_results }}
    Workspace State: {{ workspace_state }}

    EXECUTION EVALUATION FRAMEWORK:

    **Completion Assessment**: 
    Evaluate whether the current todo step has achieved its specific objective:
    - **Success Indicators**: Deliverable meets stated requirements, tool executed successfully, objective criteria satisfied
    - **Quality Threshold**: "Good enough to proceed" - optimize for progress over perfection
    - **Failure Indicators**: Tool error, incomplete data, objective not met, blocking issue for next steps

    **Progress Quality Evaluation**:
    - **Information Completeness**: Did we gather sufficient information for next steps?
    - **Deliverable Quality**: Does output meet minimum viable standard for its purpose?
    - **Dependencies Satisfied**: Are prerequisites for next todos now in place?
    - **Value Added**: Did this step meaningfully advance toward the user's goal?

    **Next Step Determination**:
    - **Linear Progression**: Standard case - move to next todo in sequence
    - **Parallel Opportunity**: Can multiple todos now execute simultaneously?
    - **Re-routing**: Should we skip or modify upcoming todos based on findings?
    - **Early Completion**: Did we achieve plan goals faster than expected?

    **Plan Completion Recognition**:
    A plan is complete when:
    - All essential objectives have been achieved
    - User's core intent has been satisfied
    - Deliverables meet or exceed stated success criteria
    - No remaining todos add significant value
    - Quality threshold for final output is met

    WORKSPACE MANAGEMENT STRATEGY:
    - **Update Principle**: Keep workspace current with latest information
    - **Organization**: Maintain logical file structure throughout execution
    - **Persistence**: Store important interim results for future reference
    - **Cleanup**: Remove or archive outdated information

    EFFICIENCY OPTIMIZATION:
    - **Momentum Preservation**: Keep execution moving forward
    - **Resource Conservation**: Avoid unnecessary tool usage or computation
    - **Value Maximization**: Prioritize high-impact activities
    - **Scope Management**: Resist scope creep that doesn't serve user goals

    QUALITY STANDARDS BY COMPLEXITY:

    **Simple Plan Execution**:
    - Immediate value delivery is primary goal
    - Minimal quality gates - trust direct execution
    - Complete quickly unless obvious errors
    - Focus on user satisfaction over optimization

    **Comprehensive Plan Execution**:
    - Multiple quality checkpoints throughout execution
    - Build confidence in deliverable quality progressively
    - Allow for iterative improvement within time bounds
    - Balance thoroughness with timely completion

    ERROR HANDLING AND RECOVERY:
    - **Tool Failures**: Assess if alternative approaches are viable
    - **Data Quality Issues**: Determine if partial results are usable
    - **Dependency Problems**: Consider re-ordering or alternative paths
    - **Scope Issues**: Adjust expectations while maintaining core value

    EXECUTION DECISION PATTERNS:

    **Standard Progression**:
    - Todo completed successfully → Move to next todo
    - All information needed for next step is available
    - Quality meets threshold for current complexity level

    **Skip Ahead**:
    - Current step revealed information making future steps unnecessary
    - User's goal can be achieved faster than originally planned
    - Redundant work detected in remaining plan

    **Plan Complete**:
    - Core user intent has been satisfied
    - Success criteria have been met
    - Remaining todos would not add meaningful value
    - Quality standard appropriate for task complexity achieved

    **Continue Current**:
    - Todo not yet complete - requires additional tool execution
    - Quality below minimum threshold for progression
    - Blocking issues prevent moving forward

    REQUIRED OUTPUT FORMAT:
    {
      "todo_completed": true | false,
      "next_todo_id": "todo-id" | null,
      "workspace_updates": ["filename1.md", "filename2.md"],
      "execution_summary": "Clear description of what was accomplished and current status",
      "plan_complete": true | false,
      "final_output": "Comprehensive final result if plan is complete" | null
    }

    EXAMPLE OUTPUTS:

    Successful Step Completion:
    {
      "todo_completed": true,
      "next_todo_id": "todo-3",
      "workspace_updates": ["ev_research_data.md"],
      "execution_summary": "Successfully researched 6 electric vehicles under $40k including Tesla Model 3, Nissan Leaf, Chevrolet Bolt, and others. Gathered comprehensive data on pricing, range, features, and expert reviews. Ready to proceed with detailed analysis.",
      "plan_complete": false,
      "final_output": null
    }

    Plan Completion:
    {
      "todo_completed": true,
      "next_todo_id": null,
      "workspace_updates": ["ev_comparison_table.md"],
      "execution_summary": "Successfully created comprehensive EV comparison table with 5 vehicles, detailed specifications, pros/cons analysis, and clear recommendations. All success criteria met.",
      "plan_complete": true,
      "final_output": "I've completed comprehensive research on electric vehicles under $40,000 and created a detailed comparison table. The analysis includes 5 top-rated EVs: Tesla Model 3, Nissan Leaf, Chevrolet Bolt EUV, Hyundai Ioniq 6, and Kia EV6. Each vehicle profile includes key specifications (range, charging time, price), comprehensive pros and cons, and value analysis. Based on the research, I've provided recommendations for different use cases. The complete comparison table with all details has been saved to your workspace as 'ev_comparison_table.md'."
    }
    "#
}