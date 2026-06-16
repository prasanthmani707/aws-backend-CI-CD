import uuid

# Global variables (module level)
request_count_by_container = {}
container_id = None

def track_container_requests(context):
    """
    Tracks requests per container and logs stats.
    Call this at start of lambda_handler.
    """
    global container_id, request_count_by_container
    
    # Set container ID if first time
    if container_id is None:
        container_id = context.aws_request_id
    
    # Initialize counter if new container
    if container_id not in request_count_by_container:
        request_count_by_container[container_id] = 0
    
    # Increment counter
    request_count_by_container[container_id] += 1
    current_request_count = request_count_by_container[container_id]
    
    # Generate unique request ID
    unique_req_id = str(uuid.uuid4())[:8]
    
    # Log container stats
    print(f"🆔 Container: {container_id[:8]} | "
          f"Req #{current_request_count} | "
          f"UUID: {unique_req_id} | "
          f"Total reqs: {current_request_count}")
    
    return current_request_count,container_id  # Return count for auto-recycle logic