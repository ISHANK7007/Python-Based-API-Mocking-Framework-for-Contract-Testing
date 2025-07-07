import json
from typing import Callable, Dict, Any

class MemoryEfficientProcessor:
    """Processes data in chunks to limit memory usage."""

    def __init__(self, chunk_size=50000):
        self.chunk_size = chunk_size

    def process_large_dataset(self, dataset_path: str, processing_func: Callable[[list], Dict]) -> Dict[str, Any]:
        """
        Process a large line-delimited JSON file in memory-efficient chunks.

        :param dataset_path: Path to the .jsonl dataset
        :param processing_func: Function that takes a chunk (list of dicts) and returns a partial result (dict)
        :return: Aggregated result dict
        """
        results = {}

        with open(dataset_path, 'r', encoding='utf-8') as f:
            chunk = []

            for i, line in enumerate(f):
                try:
                    item = json.loads(line.strip())
                    chunk.append(item)
                except json.JSONDecodeError:
                    continue  # Skip malformed lines

                if len(chunk) >= self.chunk_size:
                    chunk_results = processing_func(chunk)
                    self._merge_results(results, chunk_results)
                    chunk = []

            if chunk:
                chunk_results = processing_func(chunk)
                self._merge_results(results, chunk_results)

        return results

    def _merge_results(self, target: Dict, source: Dict):
        """
        Merge results from a processed chunk into the main results dictionary.
        Can be customized based on aggregation strategy.
        """
        for key, value in source.items():
            if key in target and isinstance(target[key], (int, float)):
                target[key] += value
            else:
                target[key] = value
