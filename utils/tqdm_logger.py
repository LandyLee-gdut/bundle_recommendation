from tqdm import tqdm as original_tqdm
import sys
import time

class TqdmLogger(original_tqdm):
    """Enhanced tqdm that logs progress to both console and file."""
    
    def __init__(self, *args, logger=None, log_interval=None, **kwargs):
        """
        Initialize TqdmLogger.
        
        Args:
            logger: Logger instance to use for logging
            log_interval: How often to log progress (e.g., every 10% or every 100 items)
        """
        self.logger = logger
        self.log_interval = log_interval or max(1, kwargs.get('total', 100) // 10)  # Default: log every 10%
        self.last_logged = 0
        self.step_name = kwargs.pop('desc', 'Progress') if 'desc' in kwargs else 'Progress'
        
        # Set file parameter to redirect tqdm output to our custom handler
        if logger:
            kwargs['file'] = sys.stdout
            
        super().__init__(*args, **kwargs)
        
        if self.logger:
            self.logger.info(f"Starting progress tracking: {self.step_name} (Total: {self.total})")
    
    def update(self, n=1):
        """Update progress and log if needed."""
        result = super().update(n)
        
        if self.logger and self.total:
            # Log at regular intervals
            if self.n - self.last_logged >= self.log_interval or self.n >= self.total:
                percentage = (self.n / self.total * 100) if self.total > 0 else 0
                self.logger.log_progress(self.step_name, self.n, self.total, 
                                       f"Rate: {self.format_dict.get('rate', 'N/A')}")
                self.last_logged = self.n
        
        return result
    
    def close(self):
        """Close progress bar and log completion."""
        if self.logger and not self.disable:
            self.logger.info(f"Completed: {self.step_name} (Total: {self.n}/{self.total})")
        super().close()

def tqdm_with_logger(iterable=None, logger=None, **kwargs):
    """Create a tqdm progress bar with logger support."""
    return TqdmLogger(iterable, logger=logger, **kwargs)
