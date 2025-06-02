import numpy as np
import yaml
from utils.ChatAPI import OpenAI, Claude
from utils.logger import Logger
from utils.functions import output_parser, process_results
from utils.metrics import findErrors, compute
from utils.tqdm_logger import tqdm_with_logger
from prompt.prompts import PromptGenerator
from tqdm import tqdm
import argparse
import os
import re


parser = argparse.ArgumentParser()
parser.add_argument('--dataset', type=str, default='electronic')
opt = parser.parse_args()

with open('config.yaml', 'r') as f:
    config = yaml.safe_load(f)

if __name__ == '__main__':

    logger = Logger(config['log_path'])
    
    # Log experiment configuration
    logger.log_experiment_config(config)
    logger.info(f"Starting bundle generation experiment for dataset: {opt.dataset}")
    
    data_path = config['data_path']+opt.dataset+'/'
    temp_path = config['temp_path']+opt.dataset+'/'
    
    logger.info(f"Loading data from: {data_path}")
    train_set = np.load(f'{data_path}training_set.npy', allow_pickle=True).item()
    test_set = np.load(f'{data_path}test_set.npy', allow_pickle=True).item()
    k_neareast_sessions = np.load(f'{data_path}TopK_related_sessions.npy', allow_pickle=True).item()
    session_items = np.load(f'{data_path}session_items.npy', allow_pickle=True).item()
    session_bundles = np.load(f'{data_path}session_bundles_deduplication.npy', allow_pickle=True).item()
    all_item_titles = np.load(f'{data_path}item_titles.npy', allow_pickle=True).item()
    
    logger.info(f"Data loaded successfully - Train: {len(train_set)}, Test: {len(test_set)}")

    # Create a new OpenAI instance
    chat = OpenAI(config['model'], config['api_key'], config['temperature'])
    logger.info(f"Initialized chat model: {config['model']}")
    
    # Create a new prompt generator
    prompt_generator = PromptGenerator(session_items, session_bundles)
    logger.info("Prompt generator initialized")

    # Construct meta info for training sessions
    prompt_generated_bundles = {} 

    for test_id in test_set.keys():
        topk_session_idx = k_neareast_sessions[test_id][0]  # consider top-1 related session
        item_titles = train_set[topk_session_idx]
        idx_item_titles = {}
        for idx, item_title in enumerate(item_titles.split('|')):
            idx_item = "product" + str(idx+1)
            idx_item_titles[idx_item] = item_title

        prompt = prompt_generator.get_Intents_generated_bundles(str(idx_item_titles))
        prompt_generated_bundles[test_id] = (topk_session_idx, prompt)

    logger.info('Start generating bundles with self-correction...')
    self_correction_res = {}
    for test_id, (topk_session_idx, prompt) in tqdm_with_logger(prompt_generated_bundles.items(), 
                                                                logger=logger, 
                                                                desc="Self-correction"):
        message = [{"role": "user", "content": prompt}]
        init_res = chat.create_chat_completion(message)
        message.append({"role": "assistant", "content": init_res})
        for i in range(3):
            message.append({"role": "user", "content": prompt_generator.get_Self_correction(i)})
            intent_res = chat.create_chat_completion(message)
            message.append({"role": "assistant", "content": intent_res})
            # early stop if the bundle is not changed
            if i == 1 and init_res == intent_res:
                logger.debug(f"Early stop for test_id {test_id} at iteration {i}")
                break
        self_correction_res[test_id] = (topk_session_idx, message)

    np.save(f'{temp_path}self_correction_res.npy', self_correction_res, allow_pickle=True)
    logger.info(f"Self-correction completed. Results saved for {len(self_correction_res)} test sessions.")

    parsered_res = dict()
    for test_id, (topk_session_idx, message) in tqdm_with_logger(self_correction_res.items(), 
                                                                 logger=logger, 
                                                                 desc="Parsing results"):
        bundle_str = None
        
        if len(message) == 6:
            bundle_str = message[-1]['content'].replace('\n', '')
        elif len(message) == 8:
            bundle_str = message[-3]['content'].replace('\n', '')
        else:
            logger.warning(f'Unexpected message length {len(message)} for test_id: {test_id}')
            continue
            
        if bundle_str:
            output_parser_res = output_parser(bundle_str)
            if output_parser_res['state_code'] == 404:
                logger.warning(f'Error when parsing test_id: {test_id}')
                continue
            elif output_parser_res['state_code'] == 200:
                bundle_dict = output_parser_res['output']
                parsered_res[test_id] = (topk_session_idx, bundle_dict)

    np.save(f'{temp_path}parsered_res.npy', parsered_res, allow_pickle=True)
    logger.info(f"Parsing completed. {len(parsered_res)} results parsed successfully.")
    
    logger.info('Start generating bundle feedback...')
    feedback_res = {}
    N_iter = config['feedback_iteration']
    
    for test_id, value in tqdm_with_logger(parsered_res.items(), 
                                          logger=logger, 
                                          desc="Bundle feedback"):
        topk_session_idx, bundle_dict = value
        Is_hallucination = False
        context = self_correction_res[test_id][1].copy()
        # iterately generate feedback for N times
        for iteration in range(N_iter):
            error_dict = findErrors(topk_session_idx, bundle_dict, session_bundles, session_items)
            if 0 in error_dict and len(error_dict)==1:
                feedback_res[test_id] = self_correction_res[test_id]
                logger.debug(f"No errors found for test_id {test_id}")
                break
            elif 5 in error_dict:
                # hallucination
                Is_hallucination = True
                logger.warning(f"Hallucination detected for test_id {test_id}")
                break      
            else:
                # Get the prompt
                feedback_prompt = prompt_generator.get_Feedback('bundle', error_dict)
                context.append({"role": "user", "content": feedback_prompt})
                # Create a new chat completion
                reply_str = chat.create_chat_completion(context)
                context.append({"role": "assistant", "content": reply_str})
                output_parser_res = output_parser(reply_str)
                if output_parser_res['state_code'] == 200:
                    bundle_dict = output_parser_res['output']
                    logger.debug(f"Applied feedback for test_id {test_id}, iteration {iteration}")
        if not Is_hallucination:
            feedback_res[test_id] = (topk_session_idx, context)

    np.save(f'{temp_path}feedback_res.npy', feedback_res, allow_pickle=True)
    logger.info(f"Bundle feedback completed. {len(feedback_res)} sessions processed.")

    logger.info('Start generating intent feedback...')

    # Generate intent for matched bundles
    intent_context = {}

    for test_id, (topk_session_idx, context) in tqdm_with_logger(feedback_res.items(), 
                                                                 logger=logger, 
                                                                 desc="Intent feedback"):
        if len(context) == 8:  # no feedback
            intent_context[test_id] = (topk_session_idx, context)
            continue
        append_intent_context = context.copy()
        append_intent_context.append({"role": "user", "content": "Given the adjusted bundles, regenerate the intents behind each bundle. Each intent should be 3-5 words. IMPORTANT: Your response MUST follow this exact JSON format without any additional text: {'bundle1': 'intent description', 'bundle2': 'intent description', ...} with each bundle key matching your previous response."})
        intent_str = chat.create_chat_completion(append_intent_context)
        append_intent_context.append({"role": "assistant", "content": intent_str})
        intent_context[test_id] = (topk_session_idx, append_intent_context)
    
    np.save(f'{temp_path}intent_context.npy', intent_context, allow_pickle=True)
    logger.info(f"Intent context generation completed. {len(intent_context)} sessions processed.")

    intent_related_bundles = {}
    for test_id, (topk_session_idx, context) in intent_context.items():
        bundle_res = output_parser(context[-3]['content'])
        intent_res = output_parser(context[-1]['content'], type='intent')
        items_session = session_items[topk_session_idx].split(',')
        ground_truth_bundles = session_bundles[topk_session_idx]

        if bundle_res['state_code'] == 404:
            logger.warning(f'Error when parsering test_id: {test_id}')
            continue
        elif bundle_res['state_code'] == 200:
            bundle_dict = bundle_res['output']
            intent_dict = intent_res['output']
            related_bundles = []
            for bundle_id, items in bundle_dict.items():
                if len(items) < 2:
                    # logger.warning(f'Empty result in test_id: {test_id}')
                    continue
                
                # Improved item extraction logic
                reidx_items = set()
                for item in items:
                    # Extract the product number using regex
                    import re
                    match = re.search(r'product(\d+)', item)
                    if match:
                        product_num = int(match.group(1))
                        if 0 < product_num <= len(items_session):
                            reidx_items.add(items_session[product_num-1])
                    else:
                        # Log warning for unexpected item format
                        logger.warning(f"Unexpected item format: {item} in test_id: {test_id}")
                
                if not reidx_items:
                    continue
                    
                for gdbundle in ground_truth_bundles:
                    bundle_list = set(gdbundle[-1].split(','))
                    if reidx_items <= bundle_list:
                        # Check if bundle_id exists in intent_dict, use a default value if not
                        intent_text = "No intent provided"
                        
                        # Try different formats to find the intent
                        if bundle_id in intent_dict:
                            intent_text = intent_dict[bundle_id]
                        elif bundle_id.lower() in intent_dict:
                            intent_text = intent_dict[bundle_id.lower()]
                        elif f"bundle{bundle_id}" in intent_dict:  # Try 'bundle1', 'bundle2', etc.
                            intent_text = intent_dict[f"bundle{bundle_id}"]
                        elif f"Bundle {bundle_id}" in intent_dict:  # Try 'Bundle 1', 'Bundle 2', etc.
                            intent_text = intent_dict[f"Bundle {bundle_id}"]
                        # Try numerical matches if the ID might be a number
                        elif bundle_id.isdigit() and f"bundle{bundle_id}" in intent_dict:
                            intent_text = intent_dict[f"bundle{bundle_id}"]
                        elif bundle_id.isdigit() and f"Bundle {bundle_id}" in intent_dict:
                            intent_text = intent_dict[f"Bundle {bundle_id}"]
                        # Try fallbacks with just the bundle part
                        elif "bundle" + bundle_id.lstrip("bundle") in intent_dict:  
                            intent_text = intent_dict["bundle" + bundle_id.lstrip("bundle")]
                        else:
                            # If we can't find a match, log a warning and use a default intent
                            logger.warning(f"Missing intent for bundle_id: {bundle_id} in test_id: {test_id}")
                            
                        if 'bundle' in bundle_id and len(bundle_id) < 10:
                            related_bundles.append((','.join(list(reidx_items)), intent_text, gdbundle[-1], gdbundle[0]))
                        else: # intent:bundle
                            related_bundles.append((','.join(list(reidx_items)), bundle_id, gdbundle[-1], gdbundle[0]))
                        break
            if len(related_bundles) != 0:
                intent_related_bundles[test_id] = (topk_session_idx, related_bundles)

    # Generate intent feedback
    intent_feedback_generation = prompt_generator.get_Intent_rater(intent_related_bundles, all_item_titles)
    np.save(f'{temp_path}intent_feedback_generation.npy', intent_feedback_generation, allow_pickle=True)

    logger.info('Rating for generated intent...')

    intent_feedback_res = {}
    intent_rater_models = config.get('intent_raters', [])
    
    def validate_model_config(model_config):
        """Validate model configuration and provide fallbacks if needed"""
        if 'openai' in model_config:
            # Check if model exists/is specified
            if not model_config['openai'].get('model'):
                print(f"Warning: Missing model in OpenAI config, using default")
                model_config['openai']['model'] = "gpt-3.5-turbo"  # Fallback model
            
            # Check API key
            if not model_config['openai'].get('api_key'):
                print(f"Warning: Missing API key in OpenAI config")
                # Try to get from environment or main config
                model_config['openai']['api_key'] = os.environ.get('OPENAI_API_KEY') or config.get('api_key', '')
                
        elif 'claude' in model_config:
            # Similar checks for Claude
            if not model_config['claude'].get('model'):
                print(f"Warning: Missing model in Claude config, using default")
                model_config['claude']['model'] = "claude-v1"  # Fallback model
            
            # Check API key
            if not model_config['claude'].get('api_key'):
                print(f"Warning: Missing API key in Claude config")
                # Try to get from environment or main config
                model_config['claude']['api_key'] = os.environ.get('ANTHROPIC_API_KEY') or config.get('api_key', '')
                
        return model_config

    intent_raters = []
    # Fallback if no valid raters are configured
    has_valid_rater = False
    
    for rate_model in intent_rater_models:
        validated_config = validate_model_config(rate_model)
        try:
            if 'openai' in validated_config:
                rater = OpenAI(
                    validated_config['openai']['model'], 
                    validated_config['openai']['api_key'], 
                    validated_config['openai'].get('temperature', 0)
                )
                intent_raters.append(rater)
                has_valid_rater = True
                logger.info(f"Initialized OpenAI rater: {validated_config['openai']['model']}")
            elif 'claude' in validated_config:
                rater = Claude(
                    validated_config['claude']['model'], 
                    validated_config['claude']['api_key'], 
                    validated_config['claude'].get('temperature', 0)
                )
                intent_raters.append(rater)
                has_valid_rater = True
                logger.info(f"Initialized Claude rater: {validated_config['claude']['model']}")
            else:
                logger.warning(f'Unknown model type in config: {validated_config}')
        except Exception as e:
            logger.error(f"Failed to initialize rater: {str(e)}")
    
    # If no valid raters, use the main model as a fallback
    if not has_valid_rater:
        logger.warning("No valid intent raters configured, using main model as fallback")
        intent_raters = [chat]  # Use the main chat model as fallback
    
    for test_id, (topk_session_idx, related_bundles) in tqdm_with_logger(intent_related_bundles.items(),
                                                                         logger=logger,
                                                                         desc="Rating intents"):
        # Skip if no related bundles
        if not related_bundles:
            logger.warning(f"No related bundles for test_id: {test_id}")
            continue
            
        try:
            metric_scores = []
            
            for rater in intent_raters:
                message = [{"role": "user", "content": intent_feedback_generation[test_id]}]
                # rate for 3 times
                scores_res = {}
                for _ in range(3):
                    try:
                        intent_feedback_str = rater.create_chat_completion(message)
                        # Add debugging output
                        logger.debug(f"Raw intent feedback for test_id {test_id}: {intent_feedback_str[:100]}...")
                        
                        intent_res = output_parser(intent_feedback_str, type='intent')['output']
                        
                        # Skip if the result is empty or malformed
                        if not intent_res:
                            logger.warning(f"Empty intent result for test_id: {test_id}")
                            continue
                            
                        for idx, (bid, intent) in enumerate(intent_res.items()):
                            if idx not in scores_res:
                                scores_res[idx] = [np.array([0,0,0]), np.array([0,0,0])]
                            
                            # Check if intent is a dictionary before accessing keys
                            if not isinstance(intent, dict):
                                logger.warning(f"Intent for bundle {bid} is not a dictionary: {intent}")
                                # Try to convert list to dict if it's a list of scores
                                if isinstance(intent, list) and all(isinstance(x, (int, float)) for x in intent):
                                    # Convert direct score list to proper format
                                    logger.warning(f"Converting score list to dict: {intent}")
                                    scores_res[idx][0] += np.array(intent)
                                    continue
                                elif isinstance(intent, str):
                                    # Skip string intents (they're not scores)
                                    continue
                            
                            try:    
                                key_list = list(intent.keys())
                                
                                # Process different return formats
                                if len(key_list) >= 2:
                                    # Standard case: two intent keys
                                    try:
                                        scores_res[idx][0] += np.array([int(i) for i in intent[key_list[0]]])
                                        scores_res[idx][1] += np.array([int(i) for i in intent[key_list[1]]])
                                    except (ValueError, TypeError) as e:
                                        logger.warning(f"Error converting scores: {e}, values: {intent[key_list[0]]}, {intent[key_list[1]]}")
                                        
                                elif len(key_list) == 1:
                                    # Only one intent key, assume it's the first intent
                                    try:
                                        scores_res[idx][0] += np.array([int(i) for i in intent[key_list[0]]])
                                        # Second intent remains 0
                                    except (ValueError, TypeError) as e:
                                        logger.warning(f"Error converting scores: {e}, value: {intent[key_list[0]]}")
                                else:
                                    # No intent keys, skip
                                    logger.warning(f"No intent keys found for bundle {bid}")
                            except AttributeError:
                                logger.warning(f"Invalid intent object for bundle {bid}: {intent}")
                        
                    except Exception as e:
                        logger.error(f"Error during intent rating: {str(e)}")
                
                if scores_res:  # Only append if we have valid scores
                    metric_scores.append(scores_res)
            
            # Only proceed if we have valid metrics
            if len(metric_scores) < 1:
                logger.warning(f"No valid metrics for test_id: {test_id}")
                continue
                
            # Rest of the processing
            # ...
            
        except Exception as e:
            logger.error(f"Error processing test_id {test_id}: {str(e)}")
    
    np.save(f'{temp_path}intent_feedback_res.npy', intent_feedback_res, allow_pickle=True)
    logger.info(f"Intent feedback completed. {len(intent_feedback_res)} sessions processed.")

    logger.info('Start generating bundles for test sessions...')
    # merge all sessions
    merged_context = {}
    for test_id, (topk_session_idx, context) in tqdm_with_logger(intent_context.items(), 
                                                                 logger=logger, 
                                                                 desc="Merging contexts"):
        if test_id in intent_feedback_res:
            merged_context[test_id] = intent_feedback_res[test_id]
        else:
            merged_context[test_id] = intent_context[test_id]

    All_context = {}
    for test_id, (topk_session_idx, context) in tqdm_with_logger(merged_context.items(), 
                                                                 logger=logger, 
                                                                 desc="Generating test bundles"):
        test_context = context.copy()
        test_context.append({"role": "user", "content": "Based on conversations above, which rules do you find when detecting bundles?"})
        rule_str = chat.create_chat_completion(test_context)
        test_context.append({"role": "assistant", "content": rule_str})

        test_prompt = prompt_generator.get_test_prompts(test_set[test_id])
        test_context.append({"role": "user", "content": test_prompt})
        test_str = chat.create_chat_completion(test_context)
        test_context.append({"role": "assistant", "content": test_str})
        test_context.append({"role": "user", "content": "Please use 3 to 5 words to generate intents behind the detected bundles, the output format is: {'bundle number':'intent'}"})
        intent_str = chat.create_chat_completion(test_context)
        test_context.append({"role": "assistant", "content": intent_str})
        
        All_context[test_id] = (topk_session_idx, test_context)

    logger.info(f"Test bundle generation completed. {len(All_context)} sessions processed.")

    logger.info('Evaluating the generated bundles...')
    bundle_res = {}

    for test_id, (topk_session_idx, context) in tqdm_with_logger(All_context.items(), 
                                                                 logger=logger, 
                                                                 desc="Evaluating bundles"):
        parsered_res = output_parser(context[-3]['content'])

        if parsered_res['state_code'] == 404:
            logger.warning(f'Error when evaluating test_id: {test_id}')
            continue 
        bundle_res[test_id] = parsered_res['output']

    np.save(f'{temp_path}bundle_res.npy', bundle_res, allow_pickle=True)
    logger.info(f"Bundle evaluation completed. {len(bundle_res)} bundles generated.")

    # remove the bundles containing only 1 product
    logger.info("Processing results to remove single-product bundles...")
    format_res = process_results(bundle_res, logger)
    logger.info(f"After filtering: {len(format_res)} valid bundles remain (removed single-product bundles)")
    
    if len(format_res) == 0:
        logger.error("No valid bundles after filtering! All bundles contain only 1 product.")
        logger.log_final_results(0.0, 0.0, 0.0, error="No valid bundles")
        exit(1)
    
    logger.info("Computing final metrics...")
    session_precision, session_recall, coverage = compute(session_items, session_bundles, format_res)
    
    # Log final results with enhanced formatting
    logger.log_final_results(session_precision, session_recall, coverage, 
                           total_test_sessions=len(test_set),
                           valid_bundles=len(format_res),
                           model=config['model'],
                           dataset=opt.dataset)







