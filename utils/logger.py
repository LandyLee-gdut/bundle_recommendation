import logging
import os
import sys
import time
from contextlib import contextmanager

class Logger(object):
    """`Logger` is a comprehensive logging system for bundle generation experiments.

    This class can show messages on standard output and write them into the
    file simultaneously. It also supports performance metrics logging and
    progress tracking.
    """

    def __init__(self, filename):
        """Initializes a new `Logger` instance.

        Args:
            filename (str): File name to create. The directory component of this
                file will be created automatically if it is not existing.
        """
        dir_name = os.path.dirname(filename)
        if not os.path.exists(dir_name):
            os.makedirs(dir_name)

        # Remove existing handlers to prevent duplication
        for handler in logging.root.handlers[:]:
            logging.root.removeHandler(handler)
            
        self.logger = logging.getLogger(filename)
        self.logger.setLevel(logging.DEBUG)
        
        # Clear any existing handlers
        self.logger.handlers.clear()
        
        formatter = logging.Formatter('%(asctime)s.%(msecs)03d: %(message)s',
                                      datefmt='%Y-%m-%d %H:%M:%S')

        # write into file
        fh = logging.FileHandler(filename, mode='a', encoding='utf-8')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(formatter)

        # show on console
        ch = logging.StreamHandler(sys.stdout)
        ch.setLevel(logging.DEBUG)
        ch.setFormatter(formatter)

        # add to Handler
        self.logger.addHandler(fh)
        self.logger.addHandler(ch)
        
        # Initialize metrics tracking
        self.start_time = time.time()
        self.step_times = {}

    def _flush(self):
        """Flush all handlers to ensure immediate writing."""
        for handler in self.logger.handlers:
            handler.flush()

    def debug(self, message):
        """Log debug message."""
        self.logger.debug(message)
        self._flush()

    def info(self, message):
        """Log info message."""
        self.logger.info(message)
        self._flush()

    def warning(self, message):
        """Log warning message."""
        self.logger.warning(message)
        self._flush()

    def error(self, message):
        """Log error message."""
        self.logger.error(message)
        self._flush()

    def critical(self, message):
        """Log critical message."""
        self.logger.critical(message)
        self._flush()
    
    def log_metrics(self, **kwargs):
        """Log performance metrics with special formatting."""
        metrics_str = "METRICS: " + ", ".join([f"{k}={v}" for k, v in kwargs.items()])
        self.info(metrics_str)
    
    def log_progress(self, step_name, current, total, additional_info=""):
        """Log progress information."""
        percentage = (current / total * 100) if total > 0 else 0
        progress_str = f"PROGRESS [{step_name}]: {current}/{total} ({percentage:.1f}%)"
        if additional_info:
            progress_str += f" - {additional_info}"
        self.info(progress_str)
    
    def start_step(self, step_name):
        """Start timing a step."""
        self.step_times[step_name] = time.time()
        self.info(f"STEP_START: {step_name}")
    
    def end_step(self, step_name):
        """End timing a step and log duration."""
        if step_name in self.step_times:
            duration = time.time() - self.step_times[step_name]
            self.info(f"STEP_END: {step_name} (Duration: {duration:.2f}s)")
            del self.step_times[step_name]
        else:
            self.warning(f"Step '{step_name}' was not started")
    
    @contextmanager
    def timed_step(self, step_name):
        """Context manager for timed steps."""
        self.start_step(step_name)
        try:
            yield
        finally:
            self.end_step(step_name)
    
    def log_experiment_config(self, config):
        """Log experiment configuration."""
        self.info("=== EXPERIMENT CONFIGURATION ===")
        for key, value in config.items():
            self.info(f"CONFIG: {key} = {value}")
        self.info("=== END CONFIGURATION ===")
    
    def log_final_results(self, precision, recall, coverage, **additional_metrics):
        """Log final experiment results with special formatting."""
        self.info("=" * 60)
        self.info("FINAL RESULTS")
        self.info("=" * 60)
        self.info(f"Precision: {precision:.6f}")
        self.info(f"Recall: {recall:.6f}")
        self.info(f"Coverage: {coverage:.6f}")
        
        if additional_metrics:
            self.info("Additional Metrics:")
            for metric, value in additional_metrics.items():
                self.info(f"  {metric}: {value}")
        
        total_time = time.time() - self.start_time
        self.info(f"Total Execution Time: {total_time:.2f} seconds")
        self.info("=" * 60)