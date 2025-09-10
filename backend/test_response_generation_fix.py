#!/usr/bin/env python3
"""
Test script to verify response generation uses workspace content.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.agents.personal_assistant.nodes import PAResponseNode

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_response_from_workspace():
    """Test that response generation uses workspace content."""
    print("🧪 Testing Response Generation from Workspace")
    print("=" * 60)
    
    # Create test node
    response_node = PAResponseNode()
    
    # Mock comprehensive workspace content (similar to the real scenario)
    test_workspace_content = """# Autonomous Task Workspace: ee9be69d-3884-42e3-9311-1d7123745dbe

## 🎯 Original Goal
research the top 10 richest people on the planet and rank by their networth, the companies they own, their date and year of birth and their horoscope sign, then group those with simillar signs at the end

### 📋 Executive Summary
This report synthesizes research on the top 10 richest people in the world, aiming to rank them by net worth, identify their companies, birthdates, and horoscope signs, and group them accordingly. The research reveals that Elon Musk currently holds the top position with a net worth fluctuating around $415 billion (September 2025 figures), owning Tesla and SpaceX.

### 🔍 Key Findings
1. Elon Musk is currently the richest person in the world, with a net worth of approximately $415 billion (September 2025), owning Tesla and SpaceX.
2. The top 10 richest people's combined net worth is estimated to be $2.13 trillion as of September 2025.
3. Jeff Bezos' net worth is around $240 billion.
4. Mark Zuckerberg's net worth is approximately $253 billion.
5. Larry Ellison's net worth is approximately $271 billion.
6. Elon Musk's horoscope sign is Cancer.
7. The United States leads in the number of billionaires, with 813 billionaires, followed by China with 473 and India with 200.

### 📊 Detailed Analysis
The research indicates the top 10 richest individuals are constantly changing, and data varies depending on the source and the date of the data retrieval. The most recent data (September 2025) from various sources, including Forbes and Indian Express, places Elon Musk at the top.

### 💡 Recommendations
1. Consolidate data from multiple reliable sources (Forbes Real-Time Billionaires List, Bloomberg Billionaires Index) to create a more accurate and up-to-date ranking of the top 10 richest individuals.
2. Prioritize finding the birthdates and horoscope signs for all individuals in the top 10 to enable the astrological grouping.

### 📋 Deliverables Created
1. A ranked list of the top 10 richest people based on available data, including net worth, company ownership (where available), birthdates, and horoscope signs.
2. An astrological grouping of the billionaires based on their horoscope signs.
3. A report highlighting the challenges of obtaining real-time data on net worth and company ownership.
"""
    
    # Set up shared state
    shared_state = {
        "user_message": "research the top 10 richest people on the planet and rank by their networth, the companies they own, their date and year of birth and their horoscope sign, then group those with simillar signs at the end",
        "original_goal": "research the top 10 richest people on the planet and rank by their networth, the companies they own, their date and year of birth and their horoscope sign, then group those with simillar signs at the end",
        "current_workspace_content": test_workspace_content,
        "synthesis_result": {"confidence": 0.95},
        "steps_completed": 9,
        "workspace_filename": "test_workspace.md",
        "thoughts": [],
        "current_tool_results": [],
        "config": type('Config', (), {'system_prompt': 'Test system prompt'})(),
        "baml_client": None
    }
    
    # Test preparation
    prep_result = await response_node.prep_async(shared_state)
    
    print("Checking preparation results...")
    
    # Verify workspace content is included
    if "workspace_content" in prep_result:
        workspace_content = prep_result["workspace_content"]
        print(f"✅ Workspace content included: {len(workspace_content)} characters")
        
        if "Executive Summary" in workspace_content and "Key Findings" in workspace_content:
            print("✅ Workspace content contains synthesis sections")
        else:
            print("❌ Workspace content missing synthesis sections")
            return False
    else:
        print("❌ Workspace content not included in prep result")
        return False
    
    # Test response generation
    print("\nTesting response generation...")

    # Debug: Test section extraction
    print("\nDebugging section extraction...")
    test_sections = ["Executive Summary", "Key Findings", "Detailed Analysis"]
    for section in test_sections:
        extracted = response_node._extract_section(test_workspace_content, section)
        print(f"Section '{section}': {len(extracted)} chars")
        if extracted:
            print(f"  Content: {extracted}")
        else:
            print(f"  No content found")

    response = await response_node.exec_async(prep_result)

    print(f"\nGenerated response length: {len(response)} characters")
    print(f"Full response:\n{response}")
    
    # Verify response uses workspace content
    expected_content = [
        "Executive Summary",
        "Key Findings", 
        "Elon Musk",
        "$415 billion",
        "Tesla and SpaceX",
        "Cancer"
    ]
    
    found_content = []
    missing_content = []
    
    for content in expected_content:
        if content in response:
            found_content.append(content)
            print(f"✅ Found: {content}")
        else:
            missing_content.append(content)
            print(f"❌ Missing: {content}")
    
    # Check for generic failure messages
    failure_indicators = [
        "I'm sorry, I am unable to synthesize",
        "I cannot perform calculations",
        "I cannot create a final deliverable",
        "I apologize for any inconvenience"
    ]
    
    has_failure_message = any(indicator in response for indicator in failure_indicators)
    
    if has_failure_message:
        print("❌ Response contains failure message instead of using workspace content")
        return False
    
    if len(found_content) >= 4:  # At least 4 out of 6 expected items
        print("✅ Response successfully uses workspace content")
        return True
    else:
        print(f"❌ Response missing too much expected content ({len(found_content)}/6)")
        return False


async def main():
    """Main test function."""
    print("🔬 Response Generation Fix Test Suite")
    print("Testing that responses use synthesized workspace content...")
    
    # Run test
    success = await test_response_from_workspace()
    
    print(f"\n🎯 TEST RESULTS:")
    print("=" * 60)
    
    if success:
        print("🎉 TEST PASSED - Response generation now uses workspace content!")
        print("\n✅ PAResponseNode now reads synthesized content from workspace!")
        print("✅ Comprehensive responses generated from research findings!")
        print("✅ No more generic failure messages when synthesis is available!")
        return True
    else:
        print("❌ TEST FAILED - Response generation still not using workspace content")
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
