from collections import defaultdict
import re


def compute(session_item, session_bundle, predictions, logger=None):
    session_precision = 0
    session_recall = 0
    coverage_item = 0
    all_hitted_bundle = 0
    
    if logger:
        logger.info(f"Computing metrics for {len(predictions)} test sessions")
    
    for test_id, pred in predictions.items():
        if len(pred) == 0:
            continue
        all_items = session_item[test_id].split(',')
        all_bundle = session_bundle[test_id]
        hitted_bundle = 0
        for bid, content in pred.items():
            try:
                reidx_items = set([all_items[int(i[-1])-1] for i in content])
            except Exception as e:
                if logger:
                    logger.error(f"Error processing test_id {test_id}: {e}")
                else:
                    print(f"Error processing test_id {test_id}: {e}")
                continue
            for bundle in all_bundle:
                bundle_list = set(bundle[-1].split(','))
                if reidx_items <= bundle_list: 
                    hitted_bundle += 1
                    union_items = len(bundle_list & reidx_items)
                    coverage_item += union_items / len(bundle_list)
                    all_hitted_bundle += 1
                    break
        session_precision += hitted_bundle / len(pred)
        session_recall += hitted_bundle / len(all_bundle)
    
    session_precision /= len(predictions)
    session_recall /= len(predictions)
    coverage = coverage_item / all_hitted_bundle if all_hitted_bundle > 0 else 0

    if logger:
        logger.info("Metrics computation completed successfully")
        logger.log_metrics(
            precision=session_precision,
            recall=session_recall,
            coverage=coverage,
            total_predictions=len(predictions),
            total_hit_bundles=all_hitted_bundle
        )

    return session_precision, session_recall, coverage

def findErrors(session_idx, generated_bundles, session_bundles, session_items):
    """
    Check the generated bundles for errors
    
    Args:
        session_idx: the session index
        generated_bundles: the generated bundles from LLM
        session_bundles: real bundles in the session
        session_items: items in the session
    
    Returns:
        error_dict: a dict of error codes and their descriptions
    """
    error_dict = {}
    
    # Type checking and conversion if needed
    if generated_bundles is None:
        error_dict[1] = "Generated bundles is None"
        return error_dict
        
    if isinstance(generated_bundles, set) or isinstance(generated_bundles, list):
        # Convert to a dictionary if it's a set or list
        try:
            temp_dict = {}
            for i, item in enumerate(generated_bundles):
                temp_dict[f'bundle{i+1}'] = item
            generated_bundles = temp_dict
        except Exception as e:
            error_dict[2] = f"Cannot convert to dictionary: {str(e)}"
            return error_dict
    
    if not isinstance(generated_bundles, dict):
        error_dict[3] = f"Generated bundles is not a dictionary, got {type(generated_bundles)}"
        return error_dict
    
    if len(generated_bundles) == 0:
        error_dict[1] = "Empty generated bundles"
        return error_dict
    
    items_session = session_items[session_idx].split(',')
    ground_truth_bundles = session_bundles[session_idx]  # Fix: using session_bundles[session_idx] consistently
    
    # For each generated bundle, check if it's a valid bundle
    for bid, items in generated_bundles.items():  
        # Check if the bundle contains hallucinated products
        is_hallucination = False
        for item in items:
            if not isinstance(item, str):
                error_dict[4] = f"Item is not a string: {item}"
                continue
                
            if 'product' in item.lower():
                try:
                    match = re.search(r'product(\d+)', item.lower())
                    if match:
                        product_num = int(match.group(1))
                        if product_num > len(items_session):
                            is_hallucination = True
                            break
                except:
                    is_hallucination = True
                    break
            else:
                is_hallucination = True
                break
        
        if is_hallucination:
            error_dict[5] = "Bundle contains hallucinated products"
    
    # Check if the ground truth bundles exist
    for bundle in ground_truth_bundles:  # Fix: using ground_truth_bundles here
        bundle_items = bundle[-1].split(',')
        found = False
        for bid, items in generated_bundles.items():
            if set(items).issubset(set(bundle_items)):
                found = True
                break
        if not found:
            error_dict[6] = "Bundle is not found in ground truth"
    
    # If no errors, add a success code
    if len(error_dict) == 0:
        error_dict[0] = "No errors"
    
    return error_dict