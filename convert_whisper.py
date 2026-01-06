from optimum.intel.openvino import OVModelForSpeechSeq2Seq
from transformers import WhisperProcessor
import torch

model_id = "openai/whisper-base"

# Load processor first
processor = WhisperProcessor.from_pretrained(model_id)

# Create dummy inputs with FIXED shapes (not dynamic)
batch_size = 1
feature_size = 80
max_length = 3000

dummy_input = {
    "input_features": torch.randn(batch_size, feature_size, max_length),
    "decoder_input_ids": torch.ones((batch_size, 1), dtype=torch.long)
}

# Export with static shapes
model = OVModelForSpeechSeq2Seq.from_pretrained(
    model_id,
    export=True,
    compile=False,
    stateful=False,
    **dummy_input  # Pass static shape inputs
)

save_dir = "./whisper-base-openvino-static"
model.save_pretrained(save_dir)
processor.save_pretrained(save_dir)

print(f"Model with static shapes saved to {save_dir}")