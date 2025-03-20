from pydub import AudioSegment
import subprocess
import os
from pypinyin import pinyin
import gradio as gr
from termcolor import colored
import subprocess
import re

LOG_FILE = "transcription_log.txt"  # 记录文件

def transcribe_audio(mp3_file):

    # 构建 whisper.cpp 的 CLI 命令
    command = [
        "./whisper.cpp/build/bin/Release/whisper-cli",  # whisper.cpp 可执行文件路径
        "-f", mp3_file,                  # 指定音频文件
        "-m", "whisper.cpp/models/ggml-small.bin"    # 使用 small 模型
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        transcription = result.stdout.strip()
        return transcription
    except subprocess.CalledProcessError as e:
        print(f"转写错误: {e.stderr}")
        return f"转写错误: {e.stderr}"
    except Exception as ex:
        return f"意外错误: {str(ex)}"

def remove_timestamps(text):
    """去掉识别文本中每行开头的时间戳"""
    pattern = r"^\[\d{2}:\d{2}:\d{2}\.\d{3} --> \d{2}:\d{2}:\d{2}\.\d{3}\]\s*"
    lines = text.splitlines()
    cleaned_lines = [re.sub(pattern, "", line) for line in lines]
    return " ".join(cleaned_lines)

def text_to_pinyin(text):
    # 将每个字的拼音转换为字符串，而不是列表
    return [item if isinstance(item, str) else "".join(item) for item in pinyin(text, strict=False)]

def unify_punctuation(text):
    """将英文标点转换为中文标点"""
    punct_map = {
        ',': '，',
        '.': '。',
        '?': '？',
        '!': '！',
        ':': '：',
        ';': '；'
    }
    for eng, chi in punct_map.items():
        text = text.replace(eng, chi)
    return text

def compare_pinyin(correct_pinyin, transcribed_pinyin, correct_text):
    correct_text_words = list(correct_text)  # 拆分正确文本为单字列表
    correct_text_result = []

    comparison_result = []
    
    correct_count = 0
    total_count = len(correct_pinyin)

    # 统一标点格式
    correct_pinyin = [unify_punctuation(p) for p in correct_pinyin]
    transcribed_pinyin = [unify_punctuation(p) for p in transcribed_pinyin]

    for i, (correct_py, transcribed_py) in enumerate(zip(correct_pinyin, transcribed_pinyin)):
        if correct_py == transcribed_py:
            comparison_result.append(correct_py)
            correct_text_result.append(correct_text_words[i])  # 对应正确文本原样添加
            correct_count += 1
        else:
            # 拼音错误标红
            comparison_result.append(f"<span style='color:red'>{transcribed_py}</span>")
            # 正确文本错误部分标红
            correct_word = correct_text_words[i] if i < len(correct_text_words) else ""
            correct_text_result.append(f"<span style='color:red'>{correct_word}</span>")

    # correct_rate = (correct_count / total_count) * 100 if total_count > 0 else 0

    # 返回修改后的正确文本、比对结果和正确率
    return " ".join(correct_text_result), " ".join(comparison_result)


def log_transcription(correct_text, correct_pinyin, transcribed_text, transcribed_pinyin, audio_file):
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"音频文件: {audio_file}\n")
        log.write(f"正确文本: {correct_text}\n")
        log.write(f"正确拼音: {' '.join(correct_pinyin)}\n")
        log.write(f"识别文本: {transcribed_text}\n")
        log.write(f"识别拼音: {' '.join(transcribed_pinyin)}\n")
        # log.write(f"拼音比对结果: {comparison_result}\n")
        # log.write(f"正确率: {correct_rate:.2f}%\n")
        log.write("="*50 + "\n\n")

def process_files(correct_text, audio_file):
    transcribed_text = transcribe_audio(audio_file)
    
    # 去掉时间戳
    cleaned_transcription = remove_timestamps(transcribed_text)
    
    correct_pinyin = text_to_pinyin(correct_text)
    transcribed_pinyin = text_to_pinyin(cleaned_transcription )
    
    # 比对拼音并标红错误部分，同时返回标红后的正确文本
    correct_text_result, transcribed_pinyin_result = compare_pinyin(
        correct_pinyin, transcribed_pinyin, correct_text
    )

    # 写入日志
    log_transcription(correct_text_result, correct_pinyin, transcribed_text, transcribed_pinyin_result, audio_file)

    # **在返回的 HTML 结果中加入标题**
    correct_text_html = f"<h3>正确文本（错误部分标红）</h3>{correct_text_result}"
    transcribed_pinyin_html = f"<h3>识别拼音（错误部分标红）</h3>{transcribed_pinyin_result}"

    return correct_text_html, transcribed_pinyin_html

def view_log():
    if not os.path.exists(LOG_FILE):
        return "暂无记录。"
    with open(LOG_FILE, "r", encoding="utf-8") as log:
        return log.read()
    
iface = gr.Interface(
    fn=process_files,
    inputs=[
        gr.Textbox(label="正确文本"),
        gr.Audio(type="filepath", label="上传MP3")
    ],
    outputs=[
        gr.HTML(),
        gr.HTML()
        # gr.Textbox(label="正确拼音"),
        # gr.Textbox(label="识别拼音"),
        # gr.HTML(label="拼音比对结果"),  # 使用 HTML 组件显示比对结果
        # gr.Textbox(label="正确率")
    ],
    title="语音发音评估系统",
    allow_flagging="never"  # 禁用 Flag 按钮
    # live=True
)

log_iface = gr.Interface(
    fn=view_log,
    inputs=[],
    outputs=[gr.Textbox(label="转写记录")],
    title="查看转写记录"
)

demo = gr.TabbedInterface([iface, log_iface], ["评估发音", "查看转写记录"])

if __name__ == "__main__":
    demo.launch()