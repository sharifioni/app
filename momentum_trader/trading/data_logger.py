"""
Async Data Logger for Paper Trading
Saves trading data to CSV without blocking the main trading loop
"""

import os
import csv
import time
import threading
import queue
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class LatencyMetrics:
    """Track latency at various stages"""
    # WebSocket latency
    ws_message_received: float = 0.0  # Timestamp when WS message received
    price_processed: float = 0.0      # Timestamp when price update processed

    # Trading latency
    signal_detected: float = 0.0      # Timestamp when signal detected
    position_opened: float = 0.0      # Timestamp when position opened
    position_closed: float = 0.0      # Timestamp when position closed

    # Calculated latencies (ms)
    ws_to_process_ms: float = 0.0
    process_to_signal_ms: float = 0.0
    signal_to_position_ms: float = 0.0

    def calculate_latencies(self):
        """Calculate latency values in milliseconds"""
        if self.ws_message_received > 0 and self.price_processed > 0:
            self.ws_to_process_ms = (self.price_processed - self.ws_message_received) * 1000
        if self.price_processed > 0 and self.signal_detected > 0:
            self.process_to_signal_ms = (self.signal_detected - self.price_processed) * 1000
        if self.signal_detected > 0 and self.position_opened > 0:
            self.signal_to_position_ms = (self.position_opened - self.signal_detected) * 1000


class AsyncDataLogger:
    """
    Non-blocking data logger that writes to CSV in background thread
    """

    def __init__(self, output_dir: str = "trading_logs"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)

        # Create session ID for this run
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Queues for async writing (non-blocking)
        self.price_queue = queue.Queue(maxsize=10000)
        self.trade_queue = queue.Queue(maxsize=1000)
        self.signal_queue = queue.Queue(maxsize=1000)
        self.latency_queue = queue.Queue(maxsize=10000)

        # File paths
        self.price_file = os.path.join(output_dir, f"prices_{self.session_id}.csv")
        self.trade_file = os.path.join(output_dir, f"trades_{self.session_id}.csv")
        self.signal_file = os.path.join(output_dir, f"signals_{self.session_id}.csv")
        self.latency_file = os.path.join(output_dir, f"latency_{self.session_id}.csv")
        self.summary_file = os.path.join(output_dir, f"summary_{self.session_id}.csv")

        # Initialize CSV files with headers
        self._init_csv_files()

        # Latency tracking
        self.latency_samples: List[Dict] = []
        self.total_price_updates = 0
        self.total_ws_latency_ms = 0.0
        self.min_latency_ms = float('inf')
        self.max_latency_ms = 0.0

        # Background writer thread
        self._running = False
        self._writer_thread = None
        self._write_interval = 5.0  # Write every 5 seconds
        self._last_write = time.time()

        # Buffers for batch writing
        self._price_buffer: List[Dict] = []
        self._trade_buffer: List[Dict] = []
        self._signal_buffer: List[Dict] = []
        self._latency_buffer: List[Dict] = []

        logger.info(f"Data logger initialized. Session: {self.session_id}")
        logger.info(f"Output directory: {output_dir}")

    def _init_csv_files(self):
        """Initialize CSV files with headers"""
        # Price history
        with open(self.price_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'datetime', 'token_id', 'event_title', 'team',
                'price', 'price_change_pct', 'volume', 'ws_latency_ms'
            ])

        # Trades
        with open(self.trade_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'trade_id', 'timestamp', 'datetime', 'token_id', 'event_id',
                'event_title', 'team', 'entry_price', 'exit_price',
                'quantity', 'amount', 'pnl', 'pnl_pct', 'exit_reason',
                'signal_strength', 'hold_duration_sec',
                'signal_latency_ms', 'execution_latency_ms'
            ])

        # Signals
        with open(self.signal_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'datetime', 'token_id', 'event_title', 'team',
                'entry_price', 'current_price', 'price_change_pct',
                'volume_change_pct', 'signal_strength', 'detection_latency_ms'
            ])

        # Latency metrics
        with open(self.latency_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'datetime', 'metric_type', 'latency_ms',
                'token_id', 'details'
            ])

    def start(self):
        """Start background writer thread"""
        if self._running:
            return

        self._running = True
        self._writer_thread = threading.Thread(target=self._writer_loop, daemon=True)
        self._writer_thread.start()
        logger.info("Background data writer started")

    def stop(self):
        """Stop background writer and flush remaining data"""
        self._running = False
        if self._writer_thread:
            self._writer_thread.join(timeout=5.0)
        self._flush_all_buffers()
        self._write_summary()
        logger.info("Data logger stopped")

    def _writer_loop(self):
        """Background loop that periodically writes buffered data"""
        while self._running:
            try:
                # Drain queues into buffers
                self._drain_queues()

                # Write if enough time has passed or buffers are large
                now = time.time()
                if (now - self._last_write >= self._write_interval or
                    len(self._price_buffer) >= 500):
                    self._flush_all_buffers()
                    self._last_write = now

                time.sleep(0.1)  # Small sleep to prevent CPU spin

            except Exception as e:
                logger.error(f"Writer loop error: {e}")

    def _drain_queues(self):
        """Move data from queues to buffers"""
        # Drain price queue
        while True:
            try:
                item = self.price_queue.get_nowait()
                self._price_buffer.append(item)
            except queue.Empty:
                break

        # Drain trade queue
        while True:
            try:
                item = self.trade_queue.get_nowait()
                self._trade_buffer.append(item)
            except queue.Empty:
                break

        # Drain signal queue
        while True:
            try:
                item = self.signal_queue.get_nowait()
                self._signal_buffer.append(item)
            except queue.Empty:
                break

        # Drain latency queue
        while True:
            try:
                item = self.latency_queue.get_nowait()
                self._latency_buffer.append(item)
            except queue.Empty:
                break

    def _flush_all_buffers(self):
        """Write all buffers to CSV files"""
        if self._price_buffer:
            self._append_to_csv(self.price_file, self._price_buffer)
            self._price_buffer = []

        if self._trade_buffer:
            self._append_to_csv(self.trade_file, self._trade_buffer)
            self._trade_buffer = []

        if self._signal_buffer:
            self._append_to_csv(self.signal_file, self._signal_buffer)
            self._signal_buffer = []

        if self._latency_buffer:
            self._append_to_csv(self.latency_file, self._latency_buffer)
            self._latency_buffer = []

    def _append_to_csv(self, filepath: str, rows: List[Dict]):
        """Append rows to CSV file with retry logic for permission errors"""
        if not rows:
            return

        max_retries = 3
        retry_delay = 0.5

        for attempt in range(max_retries):
            try:
                with open(filepath, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    for row in rows:
                        writer.writerow(row)
                return  # Success
            except PermissionError as e:
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    logger.warning(f"CSV write permission denied after {max_retries} attempts: {filepath}")
            except Exception as e:
                logger.error(f"CSV write error: {e}")
                return

    def log_price_update(
        self,
        token_id: str,
        price: float,
        event_title: str = "",
        team: str = "",
        price_change_pct: float = 0.0,
        volume: float = 0.0,
        ws_received_time: float = 0.0
    ):
        """Log a price update (non-blocking)"""
        now = time.time()

        # Calculate WS latency if we have received time
        ws_latency_ms = 0.0
        if ws_received_time > 0:
            ws_latency_ms = (now - ws_received_time) * 1000
            self._update_latency_stats(ws_latency_ms)

        record = {
            'timestamp': now,
            'datetime': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'token_id': token_id,
            'event_title': event_title[:50] if event_title else '',
            'team': team,
            'price': f"{price:.6f}",
            'price_change_pct': f"{price_change_pct*100:.4f}",
            'volume': f"{volume:.2f}",
            'ws_latency_ms': f"{ws_latency_ms:.2f}"
        }

        try:
            self.price_queue.put_nowait(record)
        except queue.Full:
            pass  # Drop if queue is full (don't block)

    def log_trade(
        self,
        trade_id: str,
        token_id: str,
        event_id: str,
        event_title: str,
        team: str,
        entry_price: float,
        exit_price: float,
        quantity: float,
        amount: float,
        pnl: float,
        pnl_pct: float,
        exit_reason: str,
        signal_strength: str,
        hold_duration: float,
        signal_latency_ms: float = 0.0,
        execution_latency_ms: float = 0.0
    ):
        """Log a completed trade (non-blocking)"""
        now = time.time()

        record = {
            'trade_id': trade_id,
            'timestamp': now,
            'datetime': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S'),
            'token_id': token_id,
            'event_id': event_id,
            'event_title': event_title[:50],
            'team': team,
            'entry_price': f"{entry_price:.6f}",
            'exit_price': f"{exit_price:.6f}",
            'quantity': f"{quantity:.4f}",
            'amount': f"{amount:.2f}",
            'pnl': f"{pnl:.2f}",
            'pnl_pct': f"{pnl_pct*100:.4f}",
            'exit_reason': exit_reason,
            'signal_strength': signal_strength,
            'hold_duration_sec': f"{hold_duration:.2f}",
            'signal_latency_ms': f"{signal_latency_ms:.2f}",
            'execution_latency_ms': f"{execution_latency_ms:.2f}"
        }

        try:
            self.trade_queue.put_nowait(record)
        except queue.Full:
            pass

    def log_signal(
        self,
        token_id: str,
        event_title: str,
        team: str,
        entry_price: float,
        current_price: float,
        price_change_pct: float,
        volume_change_pct: float,
        signal_strength: str,
        detection_latency_ms: float = 0.0
    ):
        """Log a momentum signal detection (non-blocking)"""
        now = time.time()

        record = {
            'timestamp': now,
            'datetime': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S'),
            'token_id': token_id,
            'event_title': event_title[:50],
            'team': team,
            'entry_price': f"{entry_price:.6f}",
            'current_price': f"{current_price:.6f}",
            'price_change_pct': f"{price_change_pct*100:.4f}",
            'volume_change_pct': f"{volume_change_pct*100:.4f}",
            'signal_strength': signal_strength,
            'detection_latency_ms': f"{detection_latency_ms:.2f}"
        }

        try:
            self.signal_queue.put_nowait(record)
        except queue.Full:
            pass

    def log_latency(
        self,
        metric_type: str,
        latency_ms: float,
        token_id: str = "",
        details: str = ""
    ):
        """Log a latency measurement (non-blocking)"""
        now = time.time()

        record = {
            'timestamp': now,
            'datetime': datetime.fromtimestamp(now).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
            'metric_type': metric_type,
            'latency_ms': f"{latency_ms:.3f}",
            'token_id': token_id,
            'details': details
        }

        try:
            self.latency_queue.put_nowait(record)
        except queue.Full:
            pass

    def _update_latency_stats(self, latency_ms: float):
        """Update rolling latency statistics"""
        self.total_price_updates += 1
        self.total_ws_latency_ms += latency_ms
        self.min_latency_ms = min(self.min_latency_ms, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, latency_ms)

    def get_latency_stats(self) -> Dict:
        """Get current latency statistics"""
        avg_latency = 0.0
        if self.total_price_updates > 0:
            avg_latency = self.total_ws_latency_ms / self.total_price_updates

        return {
            'total_updates': self.total_price_updates,
            'avg_latency_ms': avg_latency,
            'min_latency_ms': self.min_latency_ms if self.min_latency_ms != float('inf') else 0.0,
            'max_latency_ms': self.max_latency_ms,
        }

    def _write_summary(self):
        """Write session summary to file"""
        try:
            latency_stats = self.get_latency_stats()

            with open(self.summary_file, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['Metric', 'Value'])
                writer.writerow(['Session ID', self.session_id])
                writer.writerow(['End Time', datetime.now().strftime('%Y-%m-%d %H:%M:%S')])
                writer.writerow(['Total Price Updates', latency_stats['total_updates']])
                writer.writerow(['Avg Latency (ms)', f"{latency_stats['avg_latency_ms']:.2f}"])
                writer.writerow(['Min Latency (ms)', f"{latency_stats['min_latency_ms']:.2f}"])
                writer.writerow(['Max Latency (ms)', f"{latency_stats['max_latency_ms']:.2f}"])

            logger.info(f"Summary written to {self.summary_file}")
        except Exception as e:
            logger.error(f"Failed to write summary: {e}")

    def get_file_paths(self) -> Dict[str, str]:
        """Get paths to all output files"""
        return {
            'prices': self.price_file,
            'trades': self.trade_file,
            'signals': self.signal_file,
            'latency': self.latency_file,
            'summary': self.summary_file
        }
