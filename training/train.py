import random
from tqdm.auto import tqdm
from datasets import Dataset
from unsloth import FastLanguageModel
from trl import GRPOConfig, GRPOTrainer
import json 
from .reward_functions import * 

max_seq_length = 2048
lora_rank = 32

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name = "Qwen/Qwen3-4B-Instruct-2507",
    max_seq_length = max_seq_length,
    load_in_4bit = False,
    fast_inference = True,
    max_lora_rank = lora_rank,
    gpu_memory_utilization = 0.9
)

model = FastLanguageModel.get_peft_model(
    model,
    r = lora_rank,
    target_modules = [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    lora_alpha = lora_rank*2,
    use_gradient_checkpointing = "unsloth",
    random_state = 3407,
)

user_prompt = open("prompts/user_prompt.txt").read()
system_prompt = open("prompts/system_prompt.txt").read()


def format_dataset(value):
    email = value["email_body"]
    if "Subject" in email.split("\n")[0] :
        email = "\n".join(email.split("\n")[1:])
    json_output = value["extracted_fields"]
    json_output = json.dumps(json_output, indent = 4)
    return [
        {"role" : "system", "content" : system_prompt},
        {"role" : "user", "content" : user_prompt.format(email = email)},
        {"role" : "assistant", "content" : json_output}
    ]

def get_answer(value):
    email = value["email_body"]
    if "Subject" in email.split("\n")[0] :
        email = "\n".join(email.split("\n")[1:])
    json_output = value["extracted_fields"]
    json_output = json.dumps(json_output, indent = 4)
    return json_output + tokenizer.eos_token

def get_input_prompt(value):
    email = value["email_body"]
    if "Subject" in email.split("\n")[0] :
        email = "\n".join(email.split("\n")[1:])
    return [
        {"role" : "system", "content" : system_prompt},
        {"role" : "user", "content" : user_prompt.format(email = email)},
    ]

def format_input(email):
    if "Subject" in email.split("\n")[0] :
        email = "\n".join(email.split("\n")[1:])
    return tokenizer.apply_chat_template([
        {"role" : "system", "content" : system_prompt},
        {"role" : "user", "content" : user_prompt.format(email = email)},
    ], tokenize = False, add_generation_prompt = True)

def get_input_from_email(email):
    return [
        {"role" : "system", "content" : system_prompt},
        {"role" : "user", "content" : user_prompt.format(email = email)},
    ]

dataset = []
for i in range(3):
    dataset += json.load(open(f"./dataset/dataset{i}.json"))

for data in dataset:
    fields = data["extracted_fields"]
    if "Dr. " in fields["Provider Name"]:
        fields["Provider Name"] = fields["Provider Name"][4:]
    if ", MD" in  fields["Provider Name"]:
        fields["Provider Name"] = fields["Provider Name"][-4:]
    if "PPO" in fields["Line Of Business"]:
        fields["Line Of Business"] = fields["Line Of Business"].replace(" PPO", "").replace("PPO", "")
    if "HMO" in fields["Line Of Business"]:
        fields["Line Of Business"] = fields["Line Of Business"].replace(" HMO", "").replace("HMO", "")


chat_template = (
    "{% if messages[0]['role'] == 'system' %}"
        "{{ messages[0]['content'] + eos_token }}"
        "{% set loop_messages = messages[1:] %}"
    "{% else %}"
        "{% set loop_messages = messages %}"
    "{% endif %}"
    "{% for message in loop_messages %}"
        "{% if message['role'] == 'user' %}"
            "{{ 'User: ' + message['content'] + eos_token }}"
        "{% elif message['role'] == 'assistant' %}"
            "{{ 'Assistant: ' + message['content'] + eos_token }}"
        "{% endif %}"
    "{% endfor %}"
    "{% if add_generation_prompt %}"
        "{{ 'Assistant: ' }}"
    "{% endif %}"
)

chat_template = chat_template\
    .replace("system_prompt", f"'{system_prompt}'")

tokenizer.chat_template = chat_template

final_dataset = {
    "text" : [],
    "email" : [],
    "fields" : [],
    "prompt" : [],
    "answer" : []
}
random_idx = list(range(len(dataset)))
random.shuffle(random_idx)
for i in tqdm(random_idx):
    final_dataset["email"] .append(dataset[i]["email_body"])
    final_dataset["fields"].append(dataset[i]["extracted_fields"])
    final_dataset["text"]  .append(tokenizer.apply_chat_template(format_dataset(dataset[i]), tokenize = False))
    final_dataset["prompt"].append(tokenizer.apply_chat_template(get_input_prompt(dataset[i]), tokenize = False, add_generation_prompt = True))
    final_dataset["answer"].append(get_answer(dataset[i]))
dataset_hf = Dataset.from_dict(final_dataset)


maximum_length = 1200
max_prompt_length = maximum_length + 1
max_completion_length = max_seq_length - max_prompt_length



training_args = GRPOConfig(
    temperature = 1.0,
    learning_rate = 5e-6,
    weight_decay = 0.01,
    warmup_ratio = 0.1,
    lr_scheduler_type = "linear",
    optim = "adamw_8bit",
    logging_steps = 1,
    per_device_train_batch_size = 4,
    gradient_accumulation_steps = 1,
    num_generations = 4,
    max_prompt_length = max_prompt_length,
    max_completion_length = max_completion_length,
    max_steps = 100,
    save_steps = 100,
    report_to = "none",
    output_dir = "outputs",
)


trainer = GRPOTrainer(
    model = model,
    processing_class = tokenizer,
    reward_funcs = [
        json_format_reward,
        name_check,
        date_check,
        line_of_business_check,
        phone_number_check,
        npi_format_check,
        full_check
    ],
    args = training_args,
    train_dataset = dataset_hf,
)
trainer.train()


model.save_lora("models/grpo_lora")
