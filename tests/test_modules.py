#!/usr/bin/env python3
"""
Quick test script to verify all modules can be imported and basic functionality works.
"""

import sys
from pathlib import Path

# Add python directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'python'))

def test_imports():
    """Test that all modules can be imported."""
    print("Testing module imports...")
    
    try:
        import sample_loader
        print("✓ sample_loader")
    except Exception as e:
        print(f"✗ sample_loader: {e}")
        return False
    
    try:
        import mt_identifier
        print("✓ mt_identifier")
    except Exception as e:
        print(f"✗ mt_identifier: {e}")
        return False
    
    try:
        import volume_creator
        print("✓ volume_creator")
    except Exception as e:
        print(f"✗ volume_creator: {e}")
        return False
    
    try:
        import channel_tagger
        print("✓ channel_tagger")
    except Exception as e:
        print(f"✗ channel_tagger: {e}")
        return False
    
    try:
        import metrics_tracker
        print("✓ metrics_tracker")
    except Exception as e:
        print(f"✗ metrics_tracker: {e}")
        return False
    
    try:
        import report_generator
        print("✓ report_generator")
    except Exception as e:
        print(f"✗ report_generator: {e}")
        return False
    
    return True


def test_config_loading():
    """Test that JSON config can be loaded."""
    print("\nTesting config loading...")
    
    import json
    
    config_files = [
        'json/pipeline_config_template.json',
        'json/example_config.json'
    ]
    
    for config_file in config_files:
        config_path = Path(__file__).parent.parent / config_file
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            print(f"✓ {config_file}")
        except Exception as e:
            print(f"✗ {config_file}: {e}")
            return False
    
    return True


def test_metrics_tracker():
    """Test basic MetricsTracker functionality."""
    print("\nTesting MetricsTracker...")
    
    try:
        from metrics_tracker import MetricsTracker
        
        # Create tracker
        tracker = MetricsTracker()
        
        # Test step timing
        tracker.start_step('test_step')
        tracker.end_step('test_step', {'test_metric': 1.0})
        
        # Test summary
        summary = tracker.get_summary()
        
        print("✓ MetricsTracker basic functionality")
        return True
        
    except Exception as e:
        print(f"✗ MetricsTracker: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Pipeline v2.0 Module Tests")
    print("=" * 60)
    
    all_passed = True
    
    # Test imports
    if not test_imports():
        all_passed = False
    
    # Test config loading
    if not test_config_loading():
        all_passed = False
    
    # Test metrics tracker
    if not test_metrics_tracker():
        all_passed = False
    
    print("\n" + "=" * 60)
    if all_passed:
        print("✓ All tests passed!")
        return 0
    else:
        print("✗ Some tests failed")
        return 1


if __name__ == '__main__':
    sys.exit(main())
