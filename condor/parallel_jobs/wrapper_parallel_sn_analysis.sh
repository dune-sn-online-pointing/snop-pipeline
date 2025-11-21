#!/bin/bash
# Wrapper for SN analysis - takes batch_id as argument

BATCH_ID=$1

set -e

echo "=========================================="
echo "SN Analysis Batch $BATCH_ID"
echo "=========================================="
echo "Job start: $(date)"
echo "Hostname: $(hostname)"

# Setup LCG environment
echo "Setting up LCG environment..."
source /cvmfs/sft.cern.ch/lcg/views/LCG_106a_cuda/x86_64-el9-gcc11-opt/setup.sh

# Navigate to pipeline directory
cd /afs/cern.ch/work/e/evilla/private/dune/data-selection-pipeline

# Define category batches
case $BATCH_ID in
  0)
    CAT_RANGE="cat000001,cat000002,cat000003,cat000004,cat000005"
    echo "Processing batch 0: $CAT_RANGE"
    ;;
  1)
    CAT_RANGE="cat000006,cat000007,cat000008,cat000009,cat000010"
    echo "Processing batch 1: $CAT_RANGE"
    ;;
  2)
    CAT_RANGE="cat000011,cat000012,cat000013,cat000014,cat000015"
    echo "Processing batch 2: $CAT_RANGE"
    ;;
  3)
    CAT_RANGE="cat000016,cat000017,cat000018,cat000019,cat000020"
    echo "Processing batch 3: $CAT_RANGE"
    ;;
  4)
    CAT_RANGE="cat000021,cat000022,cat000023,cat000024,cat000025"
    echo "Processing batch 4: $CAT_RANGE"
    ;;
  5)
    CAT_RANGE="cat000026,cat000027,cat000028,cat000029,cat000030"
    echo "Processing batch 5: $CAT_RANGE"
    ;;
  6)
    CAT_RANGE="cat000031,cat000032,cat000033,cat000034,cat000035"
    echo "Processing batch 6: $CAT_RANGE"
    ;;
  7)
    CAT_RANGE="cat000036,cat000037,cat000038,cat000039,cat000040"
    echo "Processing batch 7: $CAT_RANGE"
    ;;
  8)
    CAT_RANGE="cat000041,cat000042,cat000043,cat000044,cat000045"
    echo "Processing batch 8: $CAT_RANGE"
    ;;
  9)
    CAT_RANGE="cat000046,cat000047,cat000048,cat000049,cat000050"
    echo "Processing batch 9: $CAT_RANGE"
    ;;
  10)
    CAT_RANGE="cat000051,cat000052,cat000053,cat000054,cat000055"
    echo "Processing batch 10: $CAT_RANGE"
    ;;
  11)
    CAT_RANGE="cat000056,cat000057,cat000058,cat000059,cat000060"
    echo "Processing batch 11: $CAT_RANGE"
    ;;
  12)
    CAT_RANGE="cat000061,cat000062,cat000063,cat000064,cat000065"
    echo "Processing batch 12: $CAT_RANGE"
    ;;
  13)
    CAT_RANGE="cat000066,cat000067,cat000068,cat000069,cat000070"
    echo "Processing batch 13: $CAT_RANGE"
    ;;
  14)
    CAT_RANGE="cat000071,cat000072,cat000073,cat000074,cat000075"
    echo "Processing batch 14: $CAT_RANGE"
    ;;
  15)
    CAT_RANGE="cat000076,cat000077,cat000078,cat000079,cat000080"
    echo "Processing batch 15: $CAT_RANGE"
    ;;
  16)
    CAT_RANGE="cat000081,cat000082,cat000083,cat000084,cat000085"
    echo "Processing batch 16: $CAT_RANGE"
    ;;
  17)
    CAT_RANGE="cat000086,cat000087,cat000088,cat000089,cat000090"
    echo "Processing batch 17: $CAT_RANGE"
    ;;
  18)
    CAT_RANGE="cat000091,cat000092,cat000093,cat000094,cat000095"
    echo "Processing batch 18: $CAT_RANGE"
    ;;
  19)
    CAT_RANGE="cat000096,cat000097,cat000098,cat000099,cat000100"
    echo "Processing batch 19: $CAT_RANGE"
    ;;
  20)
    CAT_RANGE="cat000101,cat000102,cat000103,cat000104,cat000105"
    echo "Processing batch 20: $CAT_RANGE"
    ;;
  21)
    CAT_RANGE="cat000106,cat000107,cat000108,cat000109,cat000110"
    echo "Processing batch 21: $CAT_RANGE"
    ;;
  22)
    CAT_RANGE="cat000111,cat000112,cat000113,cat000114,cat000115"
    echo "Processing batch 22: $CAT_RANGE"
    ;;
  23)
    CAT_RANGE="cat000116,cat000117,cat000118,cat000119,cat000120"
    echo "Processing batch 23: $CAT_RANGE"
    ;;
  24)
    CAT_RANGE="cat000121,cat000122,cat000123,cat000124,cat000125"
    echo "Processing batch 24: $CAT_RANGE"
    ;;
  25)
    CAT_RANGE="cat000126,cat000127,cat000128,cat000129,cat000130"
    echo "Processing batch 25: $CAT_RANGE"
    ;;
  26)
    CAT_RANGE="cat000131,cat000132,cat000133,cat000134,cat000135"
    echo "Processing batch 26: $CAT_RANGE"
    ;;
  27)
    CAT_RANGE="cat000136,cat000137,cat000138,cat000139,cat000140"
    echo "Processing batch 27: $CAT_RANGE"
    ;;
  28)
    CAT_RANGE="cat000141,cat000142,cat000143,cat000144,cat000145"
    echo "Processing batch 28: $CAT_RANGE"
    ;;
  29)
    CAT_RANGE="cat000146,cat000147,cat000148,cat000149,cat000150"
    echo "Processing batch 29: $CAT_RANGE"
    ;;
  30)
    CAT_RANGE="cat000151,cat000152,cat000153,cat000154,cat000155"
    echo "Processing batch 30: $CAT_RANGE"
    ;;
  31)
    CAT_RANGE="cat000156,cat000157,cat000158,cat000159,cat000160"
    echo "Processing batch 31: $CAT_RANGE"
    ;;
  32)
    CAT_RANGE="cat000161,cat000162,cat000163,cat000164,cat000165"
    echo "Processing batch 32: $CAT_RANGE"
    ;;
  33)
    CAT_RANGE="cat000166,cat000167,cat000168,cat000169,cat000170"
    echo "Processing batch 33: $CAT_RANGE"
    ;;
  34)
    CAT_RANGE="cat000171,cat000172,cat000173,cat000174,cat000175"
    echo "Processing batch 34: $CAT_RANGE"
    ;;
  35)
    CAT_RANGE="cat000176,cat000177,cat000179,cat000180,cat000181"
    echo "Processing batch 35: $CAT_RANGE"
    ;;
  36)
    CAT_RANGE="cat000182,cat000183,cat000184,cat000185,cat000186"
    echo "Processing batch 36: $CAT_RANGE"
    ;;
  37)
    CAT_RANGE="cat000187,cat000188,cat000189,cat000190,cat000191"
    echo "Processing batch 37: $CAT_RANGE"
    ;;
  38)
    CAT_RANGE="cat000192,cat000193,cat000194,cat000195,cat000196"
    echo "Processing batch 38: $CAT_RANGE"
    ;;
  39)
    CAT_RANGE="cat000197,cat000198,cat000199,cat000200,cat000201"
    echo "Processing batch 39: $CAT_RANGE"
    ;;
  40)
    CAT_RANGE="cat000202,cat000203,cat000204,cat000205,cat000206"
    echo "Processing batch 40: $CAT_RANGE"
    ;;
  41)
    CAT_RANGE="cat000207,cat000208,cat000209,cat000210,cat000211"
    echo "Processing batch 41: $CAT_RANGE"
    ;;
  42)
    CAT_RANGE="cat000212,cat000213,cat000214,cat000215,cat000216"
    echo "Processing batch 42: $CAT_RANGE"
    ;;
  43)
    CAT_RANGE="cat000217,cat000218,cat000219,cat000220,cat000221"
    echo "Processing batch 43: $CAT_RANGE"
    ;;
  44)
    CAT_RANGE="cat000222,cat000223,cat000224,cat000225,cat000226"
    echo "Processing batch 44: $CAT_RANGE"
    ;;
  45)
    CAT_RANGE="cat000227,cat000228,cat000229,cat000230,cat000231"
    echo "Processing batch 45: $CAT_RANGE"
    ;;
  46)
    CAT_RANGE="cat000232,cat000233,cat000234,cat000235,cat000236"
    echo "Processing batch 46: $CAT_RANGE"
    ;;
  47)
    CAT_RANGE="cat000237,cat000238,cat000239,cat000240,cat000241"
    echo "Processing batch 47: $CAT_RANGE"
    ;;
  48)
    CAT_RANGE="cat000242,cat000243,cat000244,cat000245,cat000246"
    echo "Processing batch 48: $CAT_RANGE"
    ;;
  49)
    CAT_RANGE="cat000247,cat000248,cat000249,cat000250,cat000251"
    echo "Processing batch 49: $CAT_RANGE"
    ;;
  50)
    CAT_RANGE="cat000252,cat000253,cat000254,cat000255,cat000256"
    echo "Processing batch 50: $CAT_RANGE"
    ;;
  51)
    CAT_RANGE="cat000257,cat000258,cat000259,cat000260,cat000261"
    echo "Processing batch 51: $CAT_RANGE"
    ;;
  52)
    CAT_RANGE="cat000262,cat000263,cat000264,cat000265,cat000266"
    echo "Processing batch 52: $CAT_RANGE"
    ;;
  53)
    CAT_RANGE="cat000267,cat000268,cat000269,cat000270,cat000271"
    echo "Processing batch 53: $CAT_RANGE"
    ;;
  54)
    CAT_RANGE="cat000272,cat000273,cat000274,cat000275,cat000276"
    echo "Processing batch 54: $CAT_RANGE"
    ;;
  55)
    CAT_RANGE="cat000277,cat000278,cat000279,cat000280,cat000281"
    echo "Processing batch 55: $CAT_RANGE"
    ;;
  56)
    CAT_RANGE="cat000282,cat000283,cat000284,cat000285,cat000286"
    echo "Processing batch 56: $CAT_RANGE"
    ;;
  57)
    CAT_RANGE="cat000287,cat000288,cat000289,cat000290,cat000291"
    echo "Processing batch 57: $CAT_RANGE"
    ;;
  58)
    CAT_RANGE="cat000292,cat000293,cat000294,cat000295,cat000296"
    echo "Processing batch 58: $CAT_RANGE"
    ;;
  59)
    CAT_RANGE="cat000297,cat000298,cat000299,cat000300,cat000301"
    echo "Processing batch 59: $CAT_RANGE"
    ;;
  60)
    CAT_RANGE="cat000302,cat000303,cat000304,cat000305,cat000306"
    echo "Processing batch 60: $CAT_RANGE"
    ;;
  61)
    CAT_RANGE="cat000307,cat000308,cat000309,cat000310,cat000311"
    echo "Processing batch 61: $CAT_RANGE"
    ;;
  62)
    CAT_RANGE="cat000312,cat000313,cat000314,cat000315,cat000316"
    echo "Processing batch 62: $CAT_RANGE"
    ;;
  63)
    CAT_RANGE="cat000317,cat000318,cat000319,cat000320,cat000321"
    echo "Processing batch 63: $CAT_RANGE"
    ;;
  64)
    CAT_RANGE="cat000322,cat000323,cat000324,cat000325,cat000326"
    echo "Processing batch 64: $CAT_RANGE"
    ;;
  65)
    CAT_RANGE="cat000327,cat000328,cat000329,cat000330,cat000331"
    echo "Processing batch 65: $CAT_RANGE"
    ;;
  66)
    CAT_RANGE="cat000332,cat000333,cat000334,cat000335,cat000336"
    echo "Processing batch 66: $CAT_RANGE"
    ;;
  67)
    CAT_RANGE="cat000337,cat000338,cat000339,cat000340,cat000341"
    echo "Processing batch 67: $CAT_RANGE"
    ;;
  68)
    CAT_RANGE="cat000342,cat000343,cat000344,cat000345,cat000346"
    echo "Processing batch 68: $CAT_RANGE"
    ;;
  69)
    CAT_RANGE="cat000347,cat000348,cat000349,cat000350,cat000351"
    echo "Processing batch 69: $CAT_RANGE"
    ;;
  70)
    CAT_RANGE="cat000352,cat000353,cat000354,cat000355,cat000356"
    echo "Processing batch 70: $CAT_RANGE"
    ;;
  71)
    CAT_RANGE="cat000357,cat000358,cat000359,cat000360,cat000361"
    echo "Processing batch 71: $CAT_RANGE"
    ;;
  72)
    CAT_RANGE="cat000362,cat000363,cat000364,cat000365,cat000366"
    echo "Processing batch 72: $CAT_RANGE"
    ;;
  73)
    CAT_RANGE="cat000367,cat000368,cat000369,cat000370,cat000371"
    echo "Processing batch 73: $CAT_RANGE"
    ;;
  74)
    CAT_RANGE="cat000372,cat000373,cat000374,cat000375,cat000376"
    echo "Processing batch 74: $CAT_RANGE"
    ;;
  75)
    CAT_RANGE="cat000377,cat000378,cat000379,cat000380,cat000381"
    echo "Processing batch 75: $CAT_RANGE"
    ;;
  76)
    CAT_RANGE="cat000382,cat000383,cat000384,cat000385,cat000387"
    echo "Processing batch 76: $CAT_RANGE"
    ;;
  77)
    CAT_RANGE="cat000394,cat000395,cat000396,cat000397,cat000398"
    echo "Processing batch 77: $CAT_RANGE"
    ;;
  78)
    CAT_RANGE="cat000399,cat000400,cat000401,cat000402,cat000403"
    echo "Processing batch 78: $CAT_RANGE"
    ;;
  79)
    CAT_RANGE="cat000404,cat000405,cat000406,cat000407,cat000408"
    echo "Processing batch 79: $CAT_RANGE"
    ;;
  80)
    CAT_RANGE="cat000409,cat000410,cat000419,cat000420,cat000421"
    echo "Processing batch 80: $CAT_RANGE"
    ;;
  81)
    CAT_RANGE="cat000422,cat000423,cat000424,cat000425,cat000426"
    echo "Processing batch 81: $CAT_RANGE"
    ;;
  82)
    CAT_RANGE="cat000427,cat000428,cat000429,cat000430,cat000431"
    echo "Processing batch 82: $CAT_RANGE"
    ;;
  83)
    CAT_RANGE="cat000432,cat000433,cat000434,cat000435,cat000436"
    echo "Processing batch 83: $CAT_RANGE"
    ;;
  84)
    CAT_RANGE="cat000437,cat000438,cat000439,cat000440,cat000441"
    echo "Processing batch 84: $CAT_RANGE"
    ;;
  85)
    CAT_RANGE="cat000442,cat000443,cat000444,cat000445,cat000446"
    echo "Processing batch 85: $CAT_RANGE"
    ;;
  86)
    CAT_RANGE="cat000447,cat000448,cat000449,cat000450,cat000451"
    echo "Processing batch 86: $CAT_RANGE"
    ;;
  87)
    CAT_RANGE="cat000452,cat000453,cat000454,cat000455,cat000456"
    echo "Processing batch 87: $CAT_RANGE"
    ;;
  88)
    CAT_RANGE="cat000457,cat000458,cat000459,cat000460,cat000461"
    echo "Processing batch 88: $CAT_RANGE"
    ;;
  89)
    CAT_RANGE="cat000462,cat000463,cat000464,cat000465,cat000466"
    echo "Processing batch 89: $CAT_RANGE"
    ;;
  90)
    CAT_RANGE="cat000467,cat000468,cat000469,cat000470,cat000471"
    echo "Processing batch 90: $CAT_RANGE"
    ;;
  91)
    CAT_RANGE="cat000472,cat000473,cat000474,cat000475,cat000476"
    echo "Processing batch 91: $CAT_RANGE"
    ;;
  92)
    CAT_RANGE="cat000477,cat000478,cat000479,cat000480,cat000481"
    echo "Processing batch 92: $CAT_RANGE"
    ;;
  93)
    CAT_RANGE="cat000482,cat000483,cat000484,cat000485,cat000486"
    echo "Processing batch 93: $CAT_RANGE"
    ;;
  94)
    CAT_RANGE="cat000487,cat000488,cat000489,cat000490,cat000491"
    echo "Processing batch 94: $CAT_RANGE"
    ;;
  95)
    CAT_RANGE="cat000492,cat000493,cat000494,cat000495,cat000496"
    echo "Processing batch 95: $CAT_RANGE"
    ;;
  96)
    CAT_RANGE="cat000497,cat000498,cat000499,cat000500,cat000501"
    echo "Processing batch 96: $CAT_RANGE"
    ;;
  97)
    CAT_RANGE="cat000502,cat000503,cat000504,cat000505,cat000506"
    echo "Processing batch 97: $CAT_RANGE"
    ;;
  98)
    CAT_RANGE="cat000507,cat000508,cat000509,cat000510,cat000511"
    echo "Processing batch 98: $CAT_RANGE"
    ;;
  99)
    CAT_RANGE="cat000512,cat000513,cat000514,cat000515,cat000516"
    echo "Processing batch 99: $CAT_RANGE"
    ;;
  100)
    CAT_RANGE="cat000517,cat000518,cat000519,cat000520,cat000521"
    echo "Processing batch 100: $CAT_RANGE"
    ;;
  101)
    CAT_RANGE="cat000522,cat000523,cat000524,cat000525,cat000526"
    echo "Processing batch 101: $CAT_RANGE"
    ;;
  102)
    CAT_RANGE="cat000527,cat000528,cat000529,cat000530,cat000531"
    echo "Processing batch 102: $CAT_RANGE"
    ;;
  103)
    CAT_RANGE="cat000532,cat000533,cat000534,cat000535,cat000536"
    echo "Processing batch 103: $CAT_RANGE"
    ;;
  104)
    CAT_RANGE="cat000537,cat000538,cat000539,cat000540,cat000541"
    echo "Processing batch 104: $CAT_RANGE"
    ;;
  105)
    CAT_RANGE="cat000542,cat000543,cat000544,cat000545,cat000546"
    echo "Processing batch 105: $CAT_RANGE"
    ;;
  106)
    CAT_RANGE="cat000547,cat000548,cat000549,cat000550,cat000551"
    echo "Processing batch 106: $CAT_RANGE"
    ;;
  107)
    CAT_RANGE="cat000552,cat000553,cat000554,cat000555,cat000556"
    echo "Processing batch 107: $CAT_RANGE"
    ;;
  108)
    CAT_RANGE="cat000557,cat000558,cat000559,cat000560,cat000561"
    echo "Processing batch 108: $CAT_RANGE"
    ;;
  109)
    CAT_RANGE="cat000562,cat000563,cat000564,cat000565,cat000566"
    echo "Processing batch 109: $CAT_RANGE"
    ;;
  110)
    CAT_RANGE="cat000568,cat000569,cat000570,cat000571,cat000572"
    echo "Processing batch 110: $CAT_RANGE"
    ;;
  111)
    CAT_RANGE="cat000573,cat000574,cat000575,cat000576,cat000577"
    echo "Processing batch 111: $CAT_RANGE"
    ;;
  112)
    CAT_RANGE="cat000578,cat000579,cat000580,cat000581,cat000582"
    echo "Processing batch 112: $CAT_RANGE"
    ;;
  113)
    CAT_RANGE="cat000583,cat000584,cat000585,cat000586,cat000587"
    echo "Processing batch 113: $CAT_RANGE"
    ;;
  114)
    CAT_RANGE="cat000588,cat000589,cat000590,cat000591,cat000592"
    echo "Processing batch 114: $CAT_RANGE"
    ;;
  115)
    CAT_RANGE="cat000593,cat000594,cat000595,cat000596,cat000598"
    echo "Processing batch 115: $CAT_RANGE"
    ;;
  116)
    CAT_RANGE="cat000600,cat000601,cat000602,cat000603,cat000604"
    echo "Processing batch 116: $CAT_RANGE"
    ;;
  117)
    CAT_RANGE="cat000605,cat000606,cat000607,cat000608,cat000609"
    echo "Processing batch 117: $CAT_RANGE"
    ;;
  118)
    CAT_RANGE="cat000610,cat000611,cat000612,cat000613,cat000614"
    echo "Processing batch 118: $CAT_RANGE"
    ;;
  119)
    CAT_RANGE="cat000615,cat000616,cat000617,cat000618,cat000619"
    echo "Processing batch 119: $CAT_RANGE"
    ;;
  120)
    CAT_RANGE="cat000620,cat000621,cat000622"
    echo "Processing batch 120: $CAT_RANGE"
    ;;
  *)
    echo "Unknown batch ID: $BATCH_ID"
    exit 1
    ;;
esac

# Run the systematic analysis for this batch
echo "Starting batch analysis..."
python3 scripts/run_systematic_sn_analysis.py \
  --cat-dir-parent /eos/project-e/ep-nu/public/sn-pointing \
  --energy-cosine-pdf /eos/home-e/evilla/dune/sn-tps/neural_networks/electron_direction/_archive_superseded/three_plane_three_plane_v18_200k_aug_20251112_114654/cosine_energy_pdf.npz \
  --output-dir results/parallel_598_cats \
  --n-es 8 \
  --n-cc 80 \
  --run-all \
  --ed-model /eos/user/e/evilla/dune/sn-tps/neural_networks/electron_direction/three_plane_v14_10k_hyperopt_20251111_175141/checkpoints/model_epoch_62_val_loss_1.1463.keras \
  --mt-model /eos/user/e/evilla/dune/sn-tps/neural_networks/mt_identifier/v26_200k/mt_fixed_20251117_150514/model_best.keras \
  --ct-model /eos/user/e/evilla/dune/sn-tps/neural_networks/channel_tagging/ct_volume_v52_batch_reload_20251116_101125/best_model.keras \
  --cat-range "$CAT_RANGE"

echo "Batch $BATCH_ID completed: $(date)"
