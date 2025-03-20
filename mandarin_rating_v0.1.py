import sys
import os
import whisper
from pypinyin import pinyin
import gradio as gr
from termcolor import colored

def transcribe_audio(mp3_file):
    model = whisper.load_model("small")
    result = model.transcribe(mp3_file)
    return result["text"]

def text_to_pinyin(text):
    # 将每个字的拼音转换为字符串，而不是列表
    return [item if isinstance(item, str) else "".join(item) for item in pinyin(text, strict=False)]

def compare_pinyin(correct_pinyin, transcribed_pinyin):
    correct_count = 0
    total_count = len(correct_pinyin)
    
    comparison_result = []
    
    for correct, transcribed in zip(correct_pinyin, transcribed_pinyin):
        if correct == transcribed:
            comparison_result.append(correct)  # 正确拼音原样添加
            correct_count += 1
        else:
            comparison_result.append(colored(transcribed, 'red'))  # 错误拼音标红

    correct_rate = (correct_count / total_count) * 100 if total_count > 0 else 0
    
    # 返回比对结果和正确率
    return " ".join(comparison_result), correct_rate

def process_files(correct_text, audio_file):
    transcribed_text = transcribe_audio(audio_file)
    correct_pinyin = text_to_pinyin(correct_text)
    transcribed_pinyin = text_to_pinyin(transcribed_text)
    
    return " ".join(correct_pinyin), " ".join(transcribed_pinyin)
    # 比对拼音并计算正确率
    comparison_result, correct_rate = compare_pinyin(correct_pinyin, transcribed_pinyin)

    
    return comparison_result, f"正确率：{correct_rate:.2f}%"

iface = gr.Interface(
    fn=process_files,
    inputs=[
        gr.Textbox(label="正确文本"),
        gr.Audio(type="filepath", label="上传MP3")
    ],
    outputs=[
        gr.Textbox(label="正确拼音"),
        gr.Textbox(label="识别拼音")
        # gr.Textbox(label="拼音比对结果"),
        # gr.Textbox(label="正确率")
    ],
    title="语音发音评估系统"
)

if __name__ == "__main__":
    iface.launch()