import multiprocessing
import os
import sys

from scipy import signal

now_dir = os.getcwd()
sys.path.append(now_dir)
print(*sys.argv[1:])
inp_root = sys.argv[1]
sr = int(sys.argv[2])
n_p = int(sys.argv[3])
exp_dir = sys.argv[4]
noparallel = sys.argv[5] == "True"
per = float(sys.argv[6])
sr_trgt = sr

import os
import traceback

import librosa
import numpy as np
from scipy.io import wavfile

from infer.lib.my_utils import load_audio
from infer.lib.slicer2 import Slicer

f = open("%s/preprocess.log" % exp_dir, "a+")


def println(strr):
    print(strr)
    f.write("%s\n" % strr)
    f.flush()


class PreProcess:
    def __init__(self, sr, sr_trgt, exp_dir, per=3.7):
        self.slicer = Slicer(
            sr=sr,
            threshold=-50,
            min_length=1500,
            min_interval=400,
            hop_size=15,
            max_sil_kept=500,
        )
        self.sr = sr
        self.bh, self.ah = signal.butter(N=5, Wn=48, btype="high", fs=self.sr)
        self.per = per
        self.overlap = 0.3
        self.tail = self.per + self.overlap
        self.max = 0.9
        self.alpha = 0.75
        self.exp_dir = exp_dir
        self.gt_wavs_dir = "%s/0_gt_wavs" % exp_dir
        self.wavs16k_dir = "%s/1_16k_wavs" % exp_dir
        os.makedirs(self.exp_dir, exist_ok=True)
        os.makedirs(self.gt_wavs_dir, exist_ok=True)
        os.makedirs(self.wavs16k_dir, exist_ok=True)
        self.sr_trgt = sr_trgt

    # Enveloping of the 0_gt segments
    def apply_envelope(self, audio):
        fade_duration = 0.005  # 8ms fade in/out duration
        fade_samples = int(fade_duration * self.sr_trgt)
        envelope = np.concatenate([
            np.linspace(0, 1, fade_samples),
            np.ones(len(audio) - 2 * fade_samples),
            np.linspace(1, 0, fade_samples)
        ])
        return audio * envelope

    # Enveloping of the 16k segments
    def apply_envelope_16k(self, audio):
        fade_duration = 0.005  # 8ms fade in/out duration
        fade_samples = int(fade_duration * 16000)
        envelope = np.concatenate([
            np.linspace(0, 1, fade_samples),
            np.ones(len(audio) - 2 * fade_samples),
            np.linspace(1, 0, fade_samples)
        ])
        return audio * envelope


    def norm_write(self, tmp_audio, idx0, idx1):
        tmp_max = np.abs(tmp_audio).max()
        if tmp_max > 2.5:
            print("%s-%s-%s-filtered" % (idx0, idx1, tmp_max))
            return


        # Resample 0_gt -> target samplerate - EXPERIMENTAL SoXr use
        tmp_audio = librosa.resample(
            tmp_audio, orig_sr=self.sr, target_sr=self.sr_trgt, res_type='soxr_vhq'
        )

        # Normalization step ( applies to both 16k and 0_gt ) 
        tmp_audio = (tmp_audio / tmp_max * (self.max * self.alpha)) + (
            1 - self.alpha
        ) * tmp_audio

        # Apply envelope for 0_gt samples
        tmp_audio = self.apply_envelope(tmp_audio)

        # Save normalized samples to 0_gt wavs folder as 32 bit float
        wavfile.write(
            "%s/%s_%s.wav" % (self.gt_wavs_dir, idx0, idx1),
            self.sr_trgt,
            tmp_audio.astype(np.float32),
        )


        # Resample 0_gt -> 16khz ones - EXPERIMENTAL SoXr use
        tmp_audio = librosa.resample(
            tmp_audio, orig_sr=self.sr, target_sr=16000, res_type='soxr_vhq'
        )


        # Apply envelope for 16k samples
        tmp_audio = self.apply_envelope_16k(tmp_audio)

        # Save normalized and resampled ( to 16khz ) samples to 16k wavs folder as 32 bit float
        wavfile.write(
            "%s/%s_%s.wav" % (self.wavs16k_dir, idx0, idx1), # 16k wavs folder
            16000,
            tmp_audio.astype(np.float32),
        )

    def pipeline(self, path, idx0):
        try:
            audio = load_audio(path, self.sr_trgt)
            # zero phased digital filter cause pre-ringing noise...
            # audio = signal.filtfilt(self.bh, self.ah, audio)
            audio = signal.lfilter(self.bh, self.ah, audio)

            idx1 = 0
            for audio in self.slicer.slice(audio):
                i = 0
                while 1:
                    start = int(self.sr_trgt * (self.per - self.overlap) * i)
                    i += 1
                    if len(audio[start:]) > self.tail * self.sr_trgt:
                        tmp_audio = audio[start : start + int(self.per * self.sr_trgt)]
                        self.norm_write(tmp_audio, idx0, idx1)
                        idx1 += 1
                    else:
                        tmp_audio = audio[start:]
                        idx1 += 1
                        break
                self.norm_write(tmp_audio, idx0, idx1)
            println("%s\t-> Success" % path)
        except:
            println("%s\t-> %s" % (path, traceback.format_exc()))

    def pipeline_mp(self, infos):
        for path, idx0 in infos:
            self.pipeline(path, idx0)

    def pipeline_mp_inp_dir(self, inp_root, n_p):
        try:
            infos = [
                ("%s/%s" % (inp_root, name), idx)
                for idx, name in enumerate(sorted(list(os.listdir(inp_root))))
            ]
            if noparallel:
                for i in range(n_p):
                    self.pipeline_mp(infos[i::n_p])
            else:
                ps = []
                for i in range(n_p):
                    p = multiprocessing.Process(
                        target=self.pipeline_mp, args=(infos[i::n_p],)
                    )
                    ps.append(p)
                    p.start()
                for i in range(n_p):
                    ps[i].join()
        except:
            println("Fail. %s" % traceback.format_exc())


def preprocess_trainset(inp_root, sr, n_p, exp_dir, per):
    pp = PreProcess(sr, sr_trgt, exp_dir, per)
    println("Starting preprocessing")
    pp.pipeline_mp_inp_dir(inp_root, n_p)
    println("Preprocessing finished")


if __name__ == "__main__":
    preprocess_trainset(inp_root, sr, n_p, exp_dir, per)
