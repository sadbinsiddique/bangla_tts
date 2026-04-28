"""
@Author : Sad Bin Siddique
@Email : sadbinsiddique@gmail.com
"""
import re
import os
import torch
import bangla
import soundfile as sf
from typing import Optional
from bnnumerizer import numerize
from bnunicodenormalizer import Normalizer
from helper.raw_data import download_file
from helper.synthsizer import Synthesizer 

bnorm=Normalizer()
root_dir = os.getcwd()

DEBUG_SAVE = True

DEBUG_GENDER = ["female", "male"]
GENDER = DEBUG_GENDER[0]

def model_loading(model_path=None, config_path=None, gender=GENDER):
    if not model_path or not config_path:
        model_path, config_path = download_file(root_dir=root_dir, output_path="models", gender=gender)
    tts_bn_model=Synthesizer(model_path, config_path, use_cuda=torch.cuda.is_available())
    return tts_bn_model

def normalize(sen):
    _words = [bnorm(word)['normalized']  for word in sen.split()]
    return " ".join([word for word in _words if word is not None])

def bangla_tts(model: Optional[Synthesizer] = None, text = "ন্যাচারাল ল্যাঙ্গুয়েজ প্রসেসিং হলো কৃত্রিম বুদ্ধিমত্তার",is_male = True, is_e2e_vits = True, log_dir = "logs/unknown.wav"):
    if model is None:
        raise ValueError("Model is not loaded. Call model_loading() first.")

    text = str(text).strip()
    if not text:
        raise ValueError("Input text is empty.")

    if(text[-1] != '।'):
        text += '।'

    # english numbers to bangla conversion
    res = re.search('[0-9]', text)
    if res is not None:
        text = bangla.convert_english_digit_to_bangla_digit(text)
    
    #replace ':' in between two bangla numbers with ' এর '
    pattern=r"[০-৯]:[০-৯]"
    matches=re.findall(pattern,text)

    for m in matches:
        r=m.replace(":"," এর ")
        text=text.replace(m,r)

    try:
        text=numerize(text)
    except Exception:
        pass

    text = normalize(text)
    if not text or not text.strip():
        raise ValueError("No valid text left after normalization.")

    sentenceEnders = re.compile('[।!?]')
    sentences = sentenceEnders.split(str(text))
    audio_list = []

    for i in range(len(sentences)):
        sentence = sentences[i].strip()
        if(not sentence):
            continue
        sentence_text = sentence + '।'
        audio_list.append(torch.as_tensor(model.tts(sentence_text)))

    if not audio_list:
        raise ValueError("Failed to synthesize audio from provided text.")

    audio = torch.cat([k for k in audio_list])
    numpy_audio = audio.detach().cpu().numpy()
    return numpy_audio

if __name__ == "__main__":
    text = 'গানটির পাণ্ডুলিপি পাওয়া যায়নি।'
    fileName = 'output/bangla_tts_v4.wav'
   
    print("Model Downloading ... ")
    model_path, config_path = download_file(root_dir=root_dir, output_path="models", gender=GENDER)
    print("Done")

    tts_bn_model = model_loading(model_path=model_path, config_path=config_path)
    audio= bangla_tts(model= tts_bn_model, text = text, is_male = False, is_e2e_vits = True)
    print("TTS Generation .... ")

    if DEBUG_SAVE:
        print(f"Saving audio file to {fileName}")
        sf.write(fileName, audio, 22050)