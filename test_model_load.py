import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
import time
import tensorflow as tf

ed_path = "/eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_three_plane_v58_200k_lr_schedule_20251118_110931/checkpoints/model_epoch_12_val_loss_0.8898.keras"
ct_path = "/eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras"

print("Loading ED model...")
t0 = time.time()
ed_model = tf.keras.models.load_model(ed_path, compile=False)
print(f"ED model loaded in {time.time()-t0:.2f}s")

print("Loading CT model...")
t0 = time.time()
ct_model = tf.keras.models.load_model(ct_path, compile=False)
print(f"CT model loaded in {time.time()-t0:.2f}s")

print("SUCCESS - Both models loaded")
