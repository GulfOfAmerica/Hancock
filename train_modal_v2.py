#!/usr/bin/env python3
"""
Hancock Fine-Tuning — Modal.com GPU Runner (v2, Modal 1.4.3 compatible)
CyberViser | Free tier: $30/month credits (~15 hours T4)

Usage:
    modal run train_modal_v2.py --dry-run
    modal run train_modal_v2.py
"""
import modal
import os

# ── Modal app definition ──────────────────────────────────────────────────────
app = modal.App("hancock-finetune-v2")

# Docker image with all ML dependencies
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install([
        "unsloth[colab-new]",
        "trl>=0.8.0", "transformers>=4.40.0", "accelerate",
        "datasets>=2.18.0", "peft", "bitsandbytes",
        "sentencepiece", "requests", "tqdm", "huggingface_hub",
    ])
)

VOLUME_NAME = "hancock-models-v2"
try:
    model_vol = modal.Volume.from_name(VOLUME_NAME, create_if_missing=True)
except Exception:
    model_vol = modal.Volume.create(VOLUME_NAME)


@app.function(
    image=image,
    gpu="T4",
    timeout=60 * 90,
    volumes={"/models": model_vol},
)
def train(dry_run: bool = False, push_hub: bool = False):
    import torch
    from unsloth import FastLanguageModel
    from trl import SFTTrainer
    from transformers import TrainingArguments
    from datasets import load_dataset

    print("\n[1/3] Loading public dataset (tatsu-lab/alpaca)...")
    ds = load_dataset("tatsu-lab/alpaca", split="train[:1000]")
    ds = ds.train_test_split(test_size=0.1)
    print(f"  ✅ Dataset: {len(ds['train']):,} train / {len(ds['test']):,} test")

    if dry_run:
        print("\n[DRY RUN] Setup OK — skipping training.")
        return {"status": "dry_run_ok", "samples": len(ds["train"])}

    print("\n[2/3] Loading Mistral-7B with Unsloth...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/mistral-7b-instruct-v0.2",
        max_seq_length=2048,
        dtype=None,
        load_in_4bit=True,
    )
    model = FastLanguageModel.get_peft_model(
        model,
        r=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                        "gate_proj", "up_proj", "down_proj"],
        lora_alpha=64,
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    def formatting_prompts_func(examples):
        texts = []
        for inst, inp, out in zip(examples["instruction"], examples["input"], examples["output"]):
            if inp:
                text = f"### Instruction:\n{inst}\n### Input:\n{inp}\n### Response:\n{out}"
            else:
                text = f"### Instruction:\n{inst}\n### Response:\n{out}"
            texts.append(text)
        return {"text": texts}

    ds = ds.map(formatting_prompts_func, batched=True)

    print("\n[3/3] Training...")
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds["train"],
        eval_dataset=ds["test"],
        dataset_text_field="text",
        max_seq_length=2048,
        packing=True,
        args=TrainingArguments(
            per_device_train_batch_size=2,
            gradient_accumulation_steps=4,
            warmup_ratio=0.05,
            num_train_epochs=1,
            learning_rate=2e-4,
            fp16=not torch.cuda.is_bf16_supported(),
            bf16=torch.cuda.is_bf16_supported(),
            logging_steps=10,
            eval_strategy="steps",
            eval_steps=50,
            save_strategy="steps",
            save_steps=100,
            save_total_limit=2,
            output_dir="/models/checkpoints",
            report_to="none",
            optim="adamw_8bit",
            weight_decay=0.01,
            lr_scheduler_type="cosine",
            seed=42,
        ),
    )
    result = trainer.train()
    print(f"  ✅ Training complete — final loss: {result.training_loss:.4f}")

    model.save_pretrained("/models/hancock_lora")
    tokenizer.save_pretrained("/models/hancock_lora")
    print("  ✅ Model saved to Modal volume 'hancock-models-v2'")

    if push_hub:
        hf_token = os.getenv("HF_TOKEN", "")
        if hf_token:
            model.push_to_hub("cyberviser/hancock-mistral-7b-lora", token=hf_token)
            tokenizer.push_to_hub("cyberviser/hancock-mistral-7b-lora", token=hf_token)
            print("  ✅ Pushed to HF Hub")
        else:
            print("  ⚠️  HF_TOKEN not set — skipping Hub push")

    return {
        "status": "success",
        "loss": result.training_loss,
        "samples": len(ds["train"]),
        "model_path": "/models/hancock_lora",
    }


@app.local_entrypoint()
def main(dry_run: bool = False, push_hub: bool = False):
    result = train.remote(dry_run=dry_run, push_hub=push_hub)
    print("\n" + "=" * 60)
    print("  TRAINING RESULT")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")
    print("\nTo download the model:")
    print("  modal volume get hancock-models-v2 hancock_lora ./hancock_lora")
