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
        Init_generated_bundles = """Detect product bundles (2+ items) from: $session_info

Output JSON only:
{"bundle1": ["product1", "product2"], "bundle2": ["product3", "product4"]}"""

        return Template(Init_generated_bundles).substitute(session_info=session_info)

    def get_Self_correction(self, idx):
        Self_correction = [
        """Generate intent (3-5 words) for each bundle:
{"bundle1": "intent here", "bundle2": "intent here"}""",
        
        """Adjust bundles using intents:
{"bundle1": ["product1", "product2"], "bundle2": ["product3", "product4"]}""",
        
        """Regenerate intents for adjusted bundles:
{"bundle1": "intent here", "bundle2": "intent here"}"""
    ]
    
        return Self_correction[idx]

    def get_Feedback(self, feedback_type, error_dict=None, intent_feedback=None):
        if feedback_type == 'bundle':
            if not error_dict:
                return "No errors found."
                
            error_types = [
                "correct",  # 0
                "empty - generate non-empty bundles",  # 1
                "wrong format - use JSON",  # 2
                "wrong type - use dictionary",  # 3
                "invalid items - use strings",  # 4
                "hallucinated products - use session products only",  # 5
                "not in ground truth"  # 6
            ]
            
            issues = []
            for error in error_dict:
                if error == 0:
                    continue
                if 0 <= error < len(error_types):
                    issues.append(f"- {error_dict[error]} are {error_types[error]}")
                else:
                    issues.append(f"- Error {error}: {error_dict[error]}")
            
            return "Issues found:\n" + "\n".join(issues) + "\nAdjust bundles accordingly."
            
        elif feedback_type == 'intent':
            if not intent_feedback:
                return "No intent issues."
                
            intent_types = ['specificity', 'relevance', 'coherence']
            issues = []
            
            for bundle_id, aspects in intent_feedback.items():
                improvements = []
                for aspect_id in aspects:
                    if 0 <= aspect_id < len(intent_types):
                        improvements.append(intent_types[aspect_id])
                    else:
                        improvements.append(f"aspect{aspect_id}")
                        
                issues.append(f"- {bundle_id}: improve {', '.join(improvements)}")
                
            return "Intent issues:\n" + "\n".join(issues) + "\nProvide updated intents."
        
        else:
            return "Unknown feedback type."

    def get_Intent_rater(self, related_bundles, item_titles):
        prompts_template = '''Rate 2 intents for each bundle on 3 metrics (1-3 scale):

Naturalness: 1=hard to read, 2=fair, 3=easy
Coverage: 1=few items covered, 2=half, 3=most  
Motivation: 1=no motivation, 2=has motivation

Bundles: $bundle_info

Output JSON only:
{
  "bundle1": {
    "intent1": [N_score, C_score, M_score],
    "intent2": [N_score, C_score, M_score]
  }
}'''
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
        test_prompts = """Detect bundles from products: $product_info

Output JSON: {"bundle1": ["product1", "product2"]}"""

        test_item_titles = {}
        for idx, item_title in enumerate(data_info.split('|')):
            idx_item = "product" + str(idx+1)
            test_item_titles[idx_item] = item_title
        
        return Template(test_prompts).substitute(product_info=str(test_item_titles))
