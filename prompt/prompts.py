from string import Template

class PromptGenerator(object):  
    def __init__(self, session_info, bundle_info):
        self.bundle_info = bundle_info
        self.session_info = session_info

    # def get_prompt(self):
    #     if self.prompt_type == 'Init_generated_bundles':
    #         return get_Intents_generated_bundles(self.session_info)
    #     elif self.prompt_type == 'Self_correction':
    #         return get_Self_correction(self.session_info)
    #     elif self.prompt_type == 'Feedback':
    #         return get_Feedback(self.session_info)
    #     else:
    #         raise ValueError('Invalid prompt type')

    def get_Intents_generated_bundles(self, session_info):
        Init_generated_bundles = """/no-think A bundle can be a set of alternative or complementary products that are purchased with a certain intent.
            Please detect bundles from a sequence of products. Each bundle must contain multiple products.

            Here are the products and descriptions: $session_info.

            IMPORTANT: Your response MUST follow this exact JSON format without any additional text or explanation:
            {
            "bundle1": ["product1", "product2", "product3"],
            "bundle2": ["product4", "product5"],
            ...
            }

            Each bundle key should be in the format 'bundle1', 'bundle2', etc.
            Each product should be referred to by its product number exactly as shown above.
            DO NOT include any explanations, comments, or additional text in your response.
        """

        return Template(Init_generated_bundles).substitute(session_info=session_info)

    def get_Self_correction(self, idx):
        Self_correction = [
        """/no-think Please generate intents behind the detected bundles using 3 to 5 words for each intent.

IMPORTANT: Your response MUST follow this exact JSON format without any additional text:
{
  "bundle1": "intent description here",
  "bundle2": "intent description here",
  ...
}

Each bundle key should be in the format 'bundle1', 'bundle2', etc.
DO NOT include any explanations, comments, or additional text in your response.""",
        
        """Given the generated intents, adjust the detected bundles with the product descriptions.

IMPORTANT: Your response MUST follow this exact JSON format without any additional text:
{
  "bundle1": ["product1", "product2", "product3"],
  "bundle2": ["product4", "product5"],
  ...
}

Each bundle key should be in the format 'bundle1', 'bundle2', etc.
Each product should be referred to by its product number exactly as shown above.
DO NOT include any explanations, comments, or additional text in your response.""",
        
        """Given the adjusted bundles, regenerate the intents behind each bundle.

IMPORTANT: Your response MUST follow this exact JSON format without any additional text:
{
  "bundle1": "intent description here",
  "bundle2": "intent description here",
  ...
}

Each bundle key should be in the format 'bundle1', 'bundle2', etc.
DO NOT include any explanations, comments, or additional text in your response."""
    ]
    
        return Self_correction[idx]

    def get_Feedback(self, feedback_type, error_dict=None, intent_feedback=None):
        if feedback_type == 'bundle':
            if not error_dict:
                return "There are no errors in the bundles."
                
            error_types = [
                "correct.",  # index 0
                "empty. Please generate non-empty bundles.",  # index 1
                "not convertible to a dictionary. Please ensure proper format.",  # index 2
                "of incorrect type. Please use a dictionary format.",  # index 3
                "invalid. Items should be strings.",  # index 4
                "containing hallucinated products. Please only use products that are in the session.",  # index 5
                "not found in ground truth. Please check bundle composition."  # index 6
            ]
            
            feed_tips = "/no-think Based on the bundles you provided, I've identified some issues:\n\n"
            
            for error in error_dict:
                # Skip the success code
                if error == 0:
                    continue
                    
                # Make sure error index is within the valid range
                if 0 <= error < len(error_types):
                    feed_tips += f"- The bundles {error_dict[error]} are {error_types[error]}\n"
                else:
                    feed_tips += f"- Error code {error}: {error_dict[error]}\n"
            
            feed_tips += "\nPlease adjust your bundles accordingly and provide the updated version."
            return feed_tips
            
        elif feedback_type == 'intent':
            if not intent_feedback:
                return "There are no issues with the intents."
                
            intent_type = ['specificity', 'relevance', 'coherence']
            feed_tips = "/no-think Based on the intents you provided, I've identified some issues:\n\n"
            
            for bundle_id, aspects in intent_feedback.items():
                feed_tips += f"- For bundle {bundle_id}, please improve the intent in terms of "
                aspect_improvements = []
                
                for aspect_id in aspects:
                    # Ensure aspect_id is within range
                    if 0 <= aspect_id < len(intent_type):
                        aspect_improvements.append(intent_type[aspect_id])
                    else:
                        aspect_improvements.append(f"aspect {aspect_id}")
                        
                feed_tips += " and ".join(aspect_improvements) + ".\n"
                
            feed_tips += "\nPlease provide updated intents for these bundles."
            return feed_tips
        
        else:
            return "Unknown feedback type."

    def get_Intent_rater(self, related_bundles, item_titles):
        prompts_template = '''/no-think
The intent should describe the customer motivation well in the purchase of the product bundles. You are asked to evaluate two intents for a bundle, using three metrics: Naturalness, Coverage, and Motivation. The details and scales of each metric are listed below:

Naturalness:
1-the intent is difficult to read and understand.
2-the intent is fair to read and understand.
3-the intent is easy to read and understand.

Coverage:
1-only a few items in the bundle are covered by the intent.
2-around half items in the bundle are covered by the intent.
3-most items in the bundle are covered by the intent.

Motivation:
1-the intent contains no motivational description.
2-the intent contains motivational description.

Following are the bundles that we ask you to evaluate:
$bundle_info

IMPORTANT: Your response MUST be a valid, complete JSON object - make sure ALL brackets are properly closed. 
Follow this exact JSON format without ANY additional text or explanations:
{
  "bundle1": {
    "intent1": [Naturalness_score, Coverage_score, Motivation_score],
    "intent2": [Naturalness_score, Coverage_score, Motivation_score]
  },
  "bundle2": {
    "intent1": [Naturalness_score, Coverage_score, Motivation_score],
    "intent2": [Naturalness_score, Coverage_score, Motivation_score]
  }
}

The JSON object MUST be properly formatted and closed with a final } bracket.
Use only numeric values (1, 2, or 3) for scores.
DO NOT include any explanations, comments, or additional text outside of this JSON structure.
'''
        meta_info = {}
        for test_id, (topk_session_idx, related_infos) in related_bundles.items():
            all_info = []
            for bundle_info in related_infos:
                idx_item_titles = {}
                for idx, item_id in enumerate(bundle_info[0].split(',')):
                    idx_item = "product" + str(idx+1)
                    idx_item_titles[idx_item] = item_titles[item_id]
                
                idx_intent = {}
                idx_intent['intent1'] = bundle_info[1]
                idx_intent['intent2'] = bundle_info[-1]
                all_info.append((str(idx_item_titles), str(idx_intent)))
            meta_info[test_id] = all_info

        intent_rater_prompt = {}
        for test_id, all_info in meta_info.items():
            bundle_info = ''
            for idx, info in enumerate(all_info):
                bundle_info += 'Bundle' + str(idx+1) + ': ' + info[0] +'\n'+ info[1] + '\n'
            intent_rater_prompt[test_id] = Template(prompts_template).substitute(bundle_info=bundle_info)

        return intent_rater_prompt

    def get_test_prompts(self, data_info):
        test_prompts = """/no-think Based on the rules, detect bundles for the below product sequence:

$product_info

IMPORTANT: Your response MUST follow this exact JSON format without any additional text:
{
  "bundle1": ["product1", "product2", "product3"],
  "bundle2": ["product4", "product5"],
  ...
}

Each bundle key should be in the format 'bundle1', 'bundle2', etc.
Each product should be referred to by its product number exactly as shown above.
DO NOT include any explanations, comments, or additional text in your response.
"""

        test_item_titles = {}
        for idx, item_title in enumerate(data_info.split('|')):
            idx_item = "product" + str(idx+1)
            test_item_titles[idx_item] = item_title
        
        return Template(test_prompts).substitute(product_info=str(test_item_titles))
