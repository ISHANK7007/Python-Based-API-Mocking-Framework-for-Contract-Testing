def _preprocess_timeline_data(self, raw_events, time_window_minutes=15):
    """Aggregate timeline events into time buckets to reduce data size"""
    aggregated = {}
    
    for event in raw_events:
        # Create time buckets
        bucket_time = event['timestamp'].replace(
            minute=(event['timestamp'].minute // time_window_minutes) * time_window_minutes,
            second=0,
            microsecond=0
        )
        
        # Create unique key for this bucket and endpoint
        key = (bucket_time, event['endpoint'], event['chaos_type'])
        
        if key not in aggregated:
            aggregated[key] = {
                'count': 0,
                'total_delay': 0,
                'min_delay': float('inf'),
                'max_delay': 0
            }
            
        # Update aggregated stats
        aggregated[key]['count'] += 1
        aggregated[key]['total_delay'] += event.get('delay', 0)
        aggregated[key]['min_delay'] = min(aggregated[key]['min_delay'], event.get('delay', 0))
        aggregated[key]['max_delay'] = max(aggregated[key]['max_delay'], event.get('delay', 0))
    
    # Convert to list format for plotting
    result = []
    for (time, endpoint, chaos_type), stats in aggregated.items():
        avg_delay = stats['total_delay'] / stats['count'] if stats['count'] > 0 else 0
        result.append({
            'timestamp': time.isoformat(),
            'endpoint': endpoint,
            'chaos_type': chaos_type,
            'count': stats['count'],
            'avg_delay': avg_delay,
            'min_delay': stats['min_delay'],
            'max_delay': stats['max_delay']
        })
    
    return result