#!/usr/bin/env python3
"""
Test script to verify the enhanced logging system works correctly
with a small subset of data.
"""

import os
import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from utils.logger import Logger
from utils.tqdm_logger import tqdm_with_logger

def test_logging_system():
    """Test the enhanced logging system with mock data."""
    
    print("🔧 Starting logging system test...")
    
    # Initialize logger
    log_path = "log/test_logging.log"
    print(f"📁 Creating logger with path: {log_path}")
    logger = Logger(log_path)
    print("✅ Logger initialized")
    
    # Test configuration logging
    test_config = {
        "dataset": "test_electronic", 
        "model": "test-model",
        "temperature": 0.6,
        "iterations": 3
    }
    print("📝 Logging experiment configuration...")
    logger.log_experiment_config(test_config)
    print("✅ Configuration logged")
    
    # Test progress tracking with tqdm
    total_items = 5
    logger.start_step("Test Processing", total_items)
    
    for i in tqdm_with_logger(range(total_items), 
                              desc="Processing items", 
                              logger=logger,
                              log_interval=1):  # Log every iteration for testing
        time.sleep(0.5)  # Simulate work
        logger.debug(f"Processed item {i+1}")
    
    logger.end_step("Test Processing", total_items)
    
    # Test metrics logging
    test_metrics = {
        "precision": 0.85,
        "recall": 0.78, 
        "f1_score": 0.81,
        "coverage": 0.92
    }
    logger.log_metrics("Test Metrics", test_metrics)
    
    # Test final results
    execution_time = 2.5
    final_results = {
        "total_processed": total_items,
        "success_rate": 0.80,
        "average_time_per_item": execution_time / total_items,
        **test_metrics
    }
    logger.log_final_results(final_results, execution_time)
    
    # Test timed step context manager
    with logger.timed_step("Database Cleanup"):
        time.sleep(1)  # Simulate cleanup work
        logger.info("Cleaned up temporary files")
    
    logger.info("✅ Logging system test completed successfully!")
    
    return log_path

if __name__ == "__main__":
    log_file = test_logging_system()
    print(f"\n📋 Test completed! Check the log file: {log_file}")
    print("🔍 Use 'cat log/test_logging.log' to view the complete log")
