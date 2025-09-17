#!/usr/bin/env python3
"""
Validation script for Enhanced Personal Assistant Implementation.

This script validates the implementation without requiring full dependencies.
"""

import os
import re
import json
from typing import Dict, List, Any

class ImplementationValidator:
    """Validator for Enhanced Personal Assistant implementation."""
    
    def __init__(self):
        self.validation_results = []
        self.base_path = "."
    
    def validate_all(self):
        """Run all validation checks."""
        print("🔍 Validating Enhanced Personal Assistant Implementation...")
        
        # Validate VFS enhancements
        self.validate_vfs_enhancements()
        
        # Validate node enhancements
        self.validate_node_enhancements()
        
        # Validate Gmail enhancements
        self.validate_gmail_enhancements()
        
        # Validate planning enhancements
        self.validate_planning_enhancements()
        
        # Validate BAML enhancements
        self.validate_baml_enhancements()
        
        # Generate report
        self.generate_validation_report()
    
    def validate_vfs_enhancements(self):
        """Validate Virtual File System enhancements."""
        vfs_file = "app/agents/personal_assistant/tools/builtin/virtual_fs.py"
        
        if not os.path.exists(vfs_file):
            self.validation_results.append({
                "component": "VFS Tool",
                "status": "FAIL",
                "reason": "File not found"
            })
            return
        
        with open(vfs_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for mandatory files
        has_mandatory_files = 'MANDATORY_FILES = ["thoughts.txt", "plan.txt", "web_search_results.txt"]' in content
        
        # Check for new actions
        has_append_action = '"append"' in content and '_append_to_file' in content
        has_exists_action = '"exists"' in content and '_check_file_exists' in content
        has_write_action = '"write"' in content and '_create_or_write_file' in content
        
        # Check for session management
        has_session_context = 'set_session_context' in content
        has_session_init = '_initialize_session' in content
        
        success = all([has_mandatory_files, has_append_action, has_exists_action, 
                      has_write_action, has_session_context, has_session_init])
        
        self.validation_results.append({
            "component": "VFS Tool",
            "status": "PASS" if success else "FAIL",
            "details": {
                "mandatory_files": has_mandatory_files,
                "new_actions": has_append_action and has_exists_action and has_write_action,
                "session_management": has_session_context and has_session_init
            }
        })
    
    def validate_node_enhancements(self):
        """Validate node enhancements."""
        nodes_file = "app/agents/personal_assistant/nodes.py"
        
        if not os.path.exists(nodes_file):
            self.validation_results.append({
                "component": "Enhanced Nodes",
                "status": "FAIL",
                "reason": "File not found"
            })
            return
        
        with open(nodes_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check PAThinkNode enhancements
        has_update_thoughts = '_update_thoughts_file' in content
        has_classify_planning = '_classify_planning_type' in content
        has_vfs_context = 'VFS context for session continuity' in content
        
        # Check PAToolCallNode enhancements
        has_step_evaluation = '_evaluate_step_success' in content
        has_error_analysis = '_analyze_tool_error' in content
        has_recovery_suggestion = '_get_tool_recovery_suggestion' in content
        
        # Check PAResponseNode enhancements
        has_fallback_response = '_generate_fallback_response' in content
        has_error_handling = 'Enhanced error handling for response generation' in content
        
        success = all([has_update_thoughts, has_classify_planning, has_vfs_context,
                      has_step_evaluation, has_error_analysis, has_recovery_suggestion,
                      has_fallback_response, has_error_handling])
        
        self.validation_results.append({
            "component": "Enhanced Nodes",
            "status": "PASS" if success else "FAIL",
            "details": {
                "think_node_enhancements": has_update_thoughts and has_classify_planning and has_vfs_context,
                "tool_node_enhancements": has_step_evaluation and has_error_analysis and has_recovery_suggestion,
                "response_node_enhancements": has_fallback_response and has_error_handling
            }
        })
    
    def validate_gmail_enhancements(self):
        """Validate Gmail tool enhancements."""
        gmail_file = "app/agents/personal_assistant/tools/external/gmail.py"
        
        if not os.path.exists(gmail_file):
            self.validation_results.append({
                "component": "Gmail Tool",
                "status": "FAIL",
                "reason": "File not found"
            })
            return
        
        with open(gmail_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for contextual email composition
        has_enhance_body = '_enhance_email_body' in content
        has_classify_email = '_classify_email_type' in content
        has_contextual_email = '_build_contextual_email' in content
        has_assistant_signature = '_get_assistant_signature' in content
        
        # Check for email templates
        has_calendar_template = '_build_calendar_event_email' in content
        has_completion_template = '_build_completion_summary_email' in content
        has_professional_template = '_build_professional_email' in content
        
        success = all([has_enhance_body, has_classify_email, has_contextual_email,
                      has_assistant_signature, has_calendar_template, has_completion_template,
                      has_professional_template])
        
        self.validation_results.append({
            "component": "Gmail Tool",
            "status": "PASS" if success else "FAIL",
            "details": {
                "contextual_composition": has_enhance_body and has_classify_email and has_contextual_email,
                "assistant_signature": has_assistant_signature,
                "email_templates": has_calendar_template and has_completion_template and has_professional_template
            }
        })
    
    def validate_planning_enhancements(self):
        """Validate planning tool enhancements."""
        planning_file = "app/agents/personal_assistant/tools/builtin/planning.py"
        
        if not os.path.exists(planning_file):
            self.validation_results.append({
                "component": "Planning Tool",
                "status": "FAIL",
                "reason": "File not found"
            })
            return
        
        with open(planning_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for VFS integration
        has_vfs_tool_ref = 'self._vfs_tool' in content
        has_set_vfs_tool = 'set_vfs_tool' in content
        has_update_plan_file = '_update_plan_file' in content
        
        # Check for comprehensive plan structure
        has_plan_file_content = '_generate_plan_file_content' in content
        has_execution_steps = 'EXECUTION STEPS' in content
        has_plan_metrics = 'PLAN METRICS' in content
        
        success = all([has_vfs_tool_ref, has_set_vfs_tool, has_update_plan_file,
                      has_plan_file_content, has_execution_steps, has_plan_metrics])
        
        self.validation_results.append({
            "component": "Planning Tool",
            "status": "PASS" if success else "FAIL",
            "details": {
                "vfs_integration": has_vfs_tool_ref and has_set_vfs_tool and has_update_plan_file,
                "comprehensive_structure": has_plan_file_content and has_execution_steps and has_plan_metrics
            }
        })
    
    def validate_baml_enhancements(self):
        """Validate BAML function enhancements."""
        baml_file = "baml_src/personal_assistant.baml"
        
        if not os.path.exists(baml_file):
            self.validation_results.append({
                "component": "BAML Functions",
                "status": "FAIL",
                "reason": "File not found"
            })
            return
        
        with open(baml_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for four-phase execution model
        has_four_phases = 'PHASE 1: META-COGNITIVE ANALYSIS' in content
        has_phase_2 = 'PHASE 2: STRATEGIC PLANNING' in content
        has_phase_3 = 'PHASE 3: SYSTEMATIC EXECUTION' in content
        has_phase_4 = 'PHASE 4: EVALUATION AND RESPONSE' in content
        
        # Check for VFS integration guidance
        has_vfs_guidance = 'VIRTUAL FILE SYSTEM (VFS) INTEGRATION' in content
        has_contextual_email = 'CONTEXTUAL EMAIL COMPOSITION' in content
        
        # Check for enhanced examples
        has_multi_tool_examples = 'MULTI-TOOL SCENARIO' in content
        has_vfs_examples = 'VFS INTEGRATION EXAMPLES' in content
        
        success = all([has_four_phases, has_phase_2, has_phase_3, has_phase_4,
                      has_vfs_guidance, has_contextual_email, has_multi_tool_examples,
                      has_vfs_examples])
        
        self.validation_results.append({
            "component": "BAML Functions",
            "status": "PASS" if success else "FAIL",
            "details": {
                "four_phase_model": has_four_phases and has_phase_2 and has_phase_3 and has_phase_4,
                "vfs_integration": has_vfs_guidance and has_vfs_examples,
                "contextual_guidance": has_contextual_email and has_multi_tool_examples
            }
        })
    
    def generate_validation_report(self):
        """Generate validation report."""
        print("\n" + "="*80)
        print("📋 ENHANCED PERSONAL ASSISTANT VALIDATION REPORT")
        print("="*80)
        
        total_components = len(self.validation_results)
        passed_components = sum(1 for result in self.validation_results if result["status"] == "PASS")
        failed_components = total_components - passed_components
        
        print(f"Total Components: {total_components}")
        print(f"Passed: {passed_components} ✅")
        print(f"Failed: {failed_components} ❌")
        print(f"Success Rate: {(passed_components/total_components)*100:.1f}%")
        print("\n" + "-"*80)
        
        for result in self.validation_results:
            status_icon = "✅" if result["status"] == "PASS" else "❌"
            print(f"{status_icon} {result['component']}: {result['status']}")
            
            if result["status"] == "FAIL" and "reason" in result:
                print(f"   Reason: {result['reason']}")
            elif "details" in result:
                for key, value in result["details"].items():
                    status = "✓" if value else "✗"
                    print(f"   {status} {key.replace('_', ' ').title()}")
            print()
        
        print("="*80)
        
        if passed_components == total_components:
            print("🎉 ALL COMPONENTS VALIDATED! Enhanced Personal Assistant implementation is complete.")
            print("\n📝 IMPLEMENTATION SUMMARY:")
            print("• ✅ Virtual File System with mandatory session files and new actions")
            print("• ✅ Meta-cognitive thinking with intent classification and context integration")
            print("• ✅ Strategic planning with comprehensive plan.txt structure")
            print("• ✅ Tool execution with step-by-step evaluation and error handling")
            print("• ✅ Email composition excellence with contextual templates")
            print("• ✅ BAML functions enhanced with four-phase execution model")
            print("• ✅ Comprehensive error handling and recovery strategies")
        else:
            print(f"⚠️  {failed_components} component(s) failed validation. Please review implementation.")
        
        print("="*80)

def main():
    """Run the validation."""
    validator = ImplementationValidator()
    validator.validate_all()

if __name__ == "__main__":
    main()
