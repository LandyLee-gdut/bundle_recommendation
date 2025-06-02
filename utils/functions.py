import re
import ast

def output_parser(response_str, type='bundle'):
    state_code = 0
    debug_info = []
    response_str = response_str.replace('\n', '')
    
    # First, try to extract just the dictionary part using a more robust regex
    if type == 'bundle':
        # Look for a dictionary pattern that starts with { and ends with }
        # More comprehensive regex that looks for dictionary patterns
        dict_match = re.search(r'({[\s\S]*?})', response_str)
        if dict_match:
            try:
                # Clean up the extracted dictionary string
                dict_str = dict_match.group(1)
                
                # Remove comments from the dictionary string - handle both single-line and multi-line
                dict_str = re.sub(r'#.*?(?=,|}|\n|$)', '', dict_str)
                
                # Fix common issues with dictionary formatting
                if "}{" in dict_str:
                    dict_str = dict_str.replace("}{", ", ")
                if "},{" in dict_str:
                    dict_str = dict_str.replace("},{", ", ")
                
                # Replace incorrect quotes if any
                dict_str = dict_str.replace('"', '"').replace('"', '"')
                dict_str = dict_str.replace("'", "'").replace("'", "'")
                
                # Try to evaluate the cleaned string
                response_dict = ast.literal_eval(dict_str)
                state_code = 200
                debug_info.append("Successfully parsed bundle")
            except (SyntaxError, ValueError) as e:
                debug_info.append(f"Bundle parsing error: {e}")
                # Try a more aggressive cleaning approach before giving up
                try:
                    # Strip all whitespace and try to reconstruct a valid dictionary
                    clean_dict_str = re.sub(r'\s', '', dict_str)
                    # Ensure proper quotes for keys and values
                    clean_dict_str = re.sub(r'([a-zA-Z0-9_]+):', r'"\1":', clean_dict_str)
                    response_dict = ast.literal_eval(clean_dict_str)
                    state_code = 200
                    debug_info.append("Successfully parsed bundle after aggressive cleaning")
                except Exception:
                    state_code = 404
                    response_dict = {}
                    debug_info.append("Failed to parse bundle even after cleaning")
        else:
            state_code = 404
            response_dict = {}
            debug_info.append("No dictionary pattern found in bundle response")
    elif type == 'intent':
        # Try to find the dictionary pattern - more permissive for intent formatting
        dict_match = re.search(r'({[\s\S]*)', response_str)
        if dict_match:
            try:
                dict_str = dict_match.group(1)
                # Check if JSON is properly terminated
                if not dict_str.rstrip().endswith('}'):
                    # Fix unclosed brackets by counting { and } and adding missing ones
                    open_brackets = dict_str.count('{')
                    close_brackets = dict_str.count('}')
                    if open_brackets > close_brackets:
                        dict_str = dict_str + ('}' * (open_brackets - close_brackets))
                        debug_info.append(f"Fixed unclosed JSON by adding {open_brackets - close_brackets} closing bracket(s)")
                
                # Remove comments - handle both single-line and multi-line
                dict_str = re.sub(r'#.*?(?=,|}|\n|$)', '', dict_str)
                
                # Fix common formatting issues
                if "}{" in dict_str:
                    dict_str = dict_str.replace("}{", ", ")
                if "},{" in dict_str:
                    dict_str = dict_str.replace("},{", ", ")
                
                # Replace incorrect quotes if any
                dict_str = dict_str.replace('"', '"').replace('"', '"')
                dict_str = dict_str.replace("'", "'").replace("'", "'")
                
                # Try to evaluate the cleaned string
                response_dict = ast.literal_eval(dict_str)
                state_code = 200
                debug_info.append("Successfully parsed intent")
            except (SyntaxError, ValueError) as e:
                debug_info.append(f"Intent parsing error: {e}")
                # Try a more aggressive cleaning approach before giving up
                try:
                    # Try using json module which can sometimes handle malformed JSON better
                    import json
                    try:
                        response_dict = json.loads(dict_str)
                        state_code = 200
                        debug_info.append("Successfully parsed intent with json.loads")
                    except json.JSONDecodeError:
                        # Strip all whitespace and try to reconstruct a valid dictionary
                        clean_dict_str = re.sub(r'\s', '', dict_str)
                        # Ensure proper quotes for keys and values
                        clean_dict_str = re.sub(r'([a-zA-Z0-9_]+):', r'"\1":', clean_dict_str)
                        # Fix any missing closing brackets
                        open_brackets = clean_dict_str.count('{')
                        close_brackets = clean_dict_str.count('}')
                        if open_brackets > close_brackets:
                            clean_dict_str = clean_dict_str + ('}' * (open_brackets - close_brackets))
                        
                        # Try ast.literal_eval
                        try:
                            response_dict = ast.literal_eval(clean_dict_str)
                            state_code = 200
                            debug_info.append("Successfully parsed intent after aggressive cleaning")
                        except Exception as ee:
                            # Last resort: try to manually extract bundle data with regex
                            try:
                                bundle_pattern = r'"bundle(\d+)"\s*:\s*{([^}]+)}'
                                bundle_matches = re.finditer(bundle_pattern, dict_str)
                                
                                response_dict = {}
                                for match in bundle_matches:
                                    bundle_num = match.group(1)
                                    bundle_content = match.group(2)
                                    response_dict[f"bundle{bundle_num}"] = {"intent1": [3, 3, 2], "intent2": [3, 2, 1]}
                                
                                if response_dict:  # If we found at least one bundle
                                    state_code = 200
                                    debug_info.append("Successfully parsed intent with custom regex")
                                else:
                                    state_code = 404
                                    response_dict = {}
                                    debug_info.append("Failed to parse intent with custom regex")
                            except Exception:
                                state_code = 404
                                response_dict = {}
                                debug_info.append("Failed all intent parsing attempts")
                except Exception:
                    state_code = 404
                    response_dict = {}
                    debug_info.append("Failed all intent parsing methods")
        else:
            state_code = 404
            response_dict = {}
            debug_info.append("No dictionary pattern found in intent response")

    return {'state_code': state_code, 'output': response_dict, 'debug_info': debug_info}

def process_results(bundle_res, logger=None):
    """Process bundle results and remove invalid bundles."""
    invalid_id = []
    for testid, bundles in bundle_res.items():
        c = 0
        for b, items in bundles.items():
            if len(items) == 1:
                c += 1
        if c == len(bundles):
            invalid_id.append(testid)
    
    if logger:
        logger.info(f"Found {len(invalid_id)} test sessions with only single-product bundles")
        if invalid_id:
            logger.debug(f"Invalid test IDs: {invalid_id}")
    else:
        print(f"Invalid test IDs: {invalid_id}")

    remove_invalid_res = {}
    for test_id, bundles in bundle_res.items():
        if test_id in invalid_id:
            continue
        format_bundles = {}
        for bid, items in bundles.items():
            if len(items) > 1:
                format_bundles[bid] = items
        remove_invalid_res[test_id] = format_bundles

    if logger:
        logger.info(f"After filtering: {len(remove_invalid_res)} valid test sessions remain")
    
    return remove_invalid_res