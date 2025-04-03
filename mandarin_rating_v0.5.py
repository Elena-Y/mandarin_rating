import streamlit as st
import subprocess
import os
from pypinyin import pinyin
import gradio as gr
from termcolor import colored
import subprocess
import re
import argparse
import markdown
from markdown.extensions.tables import TableExtension
from pypinyin import pinyin, Style
from pydub import AudioSegment
import tempfile

LOG_FILE = "transcription_log.txt"  # 记录文件

# 处理音频文件的转换
def convert_audio(file_path, output_format="wav"):
    audio = AudioSegment.from_file(file_path)
    temp_wav = tempfile.NamedTemporaryFile(delete=False, suffix=f".{output_format}")
    audio.export(temp_wav.name, format=output_format)
    return temp_wav.name

def convert_markdown_table_to_html(md_table):
    """将 Markdown 表格转换为 HTML 表格"""
    return markdown.markdown(md_table, extensions=[TableExtension()])


from openai import OpenAI

def generate_correction_report(correct_text, transcribed_text, correct_pinyin, transcribed_pinyin):
    """使用 LLM 对比正确文本和转写文本，生成纠错报告"""
    
    client = OpenAI(
                    #中转的url地址
                    base_url='https://tbnx.plus7.plus/v1',
                    #修改为自己生成的key
                    api_key='sk-QZNCaLmy0ggUsIfbw2doCoeWqLLuoM0FpUFaSCmz8xgCmwt7'
    )
 
    prompt = f"""
    你是一位专业的中文语言评测专家，现在需要对一段 **课文朗读** 进行自动评分。  

    ### **📌 评分标准**  

    **（1）内容准确：25分**  
    - 朗读内容是否忠实于课文。  

    **（2）其他词语及句子：25分**  
    - 普通词语拼音错误，每个错误扣 **1 分**，最多扣 **25 分**。  

    **（3）语音面貌：25分**  
    - 评估 **发音准确性** 和 **声调**，根据错误类型合理扣分（而不是简单按错误个数扣分）。  

    **（4）整体表达：25分**  
    - 评估 **流利性** 和 **逻辑性**，是否有停顿、断句等影响表达的现象。  

    ---

    ### **📌 任务要求**  
    1. **将【正确文本】【转写文本】转写为拼音并作比对**，找出所有错误，并根据评分标准扣分，提供详细的纠错说明，以 HTML 表格形式返回，确保在 HTML 界面中正确显示。表格列名包括：错误拼音、正确拼音、对应文本、错误类型（如：声母错误、韵母错误、声调错误、拼音缺失、重复拼音等）、扣分、发音注意要点。
    2. **返回最终得分（满分 100）和小项得分（参考评分标准）**，并解释扣分原因。  
    3. **必须以 HTML 表格格式返回，确保在 HTML 界面中正确显示**。  
    4. **如果完全正确，返回 `<p>🎉 朗读完全正确，得分：100/100</p>`**。

    ---

    ### **【正确文本】**
     {correct_text}

    ### **【转写文本】**
    {transcribed_text}

    请直接返回 **HTML 格式** 的评分结果：
    """
    
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[{"role": "system", "content": "你是一个专业的中文语言专家"},
                  {"role": "user", "content": prompt}],
        stream=False
    )
    
    report = response.choices[0].message.content
    
    # 确保 Markdown 表格转为 HTML（如果模型输出 Markdown 表格，这里做个保险）
    if "|" in report:  
        report = convert_markdown_table_to_html(report)  

    # 确保表格以 HTML 格式显示
    # report_html = f"<h3>纠错报告</h3>{report.replace('|', '&#124;')}"  
    return report


def transcribe_audio(mp3_file):

    # 构建 whisper.cpp 的 CLI 命令
    command = [
        "./whisper.cpp/build/bin/Release/whisper-cli",  # whisper.cpp 可执行文件路径
        "-f", mp3_file,                  # 指定音频文件
        "-m", "whisper.cpp/models/ggml-small.bin",    # 使用 small 模型
        "-l", "zh"                         # 强制指定语言为汉语
    ]

    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="ignore")
        raw_text = result.stdout.strip()
        return remove_timestamps(raw_text)  # 去掉时间戳
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
    # 将拼音的字母连接起来，并用空格分隔拼音词
    return ' '.join([''.join(item) for item in pinyin(text, style='normal', heteronym=False)])

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
            correct_text_result.append(correct_text[i])  # 对应正确文本原样添加
            correct_count += 1
        else:
            # 拼音错误标红
            comparison_result.append(f"<span style='color:red'>{transcribed_py}</span>")
            # 正确文本错误部分标红
            correct_word = correct_text[i] if i < len(correct_text) else ""
            correct_text_result.append(f"<span style='color:red'>{correct_word}</span>")

    correct_rate = (correct_count / total_count) * 100 if total_count > 0 else 0

    # 返回修改后的正确文本、比对结果和正确率
    return "".join(correct_text_result), " ".join(comparison_result)
    # return "".join(correct_text), " ".join(transcribed_pinyin)


def log_transcription(correct_text, correct_pinyin, transcribed_text, transcribed_pinyin, correction_report, audio_file):
    log_content = f"""音频文件: {audio_file}
正确文本: {correct_text}
识别文本: {transcribed_text}
正确拼音: {correct_pinyin}
识别拼音: {transcribed_pinyin}
纠错报告:
{correction_report}
    """
    # 如果你还想保存到文件，也可以保留这个操作
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(log_content)
        log.write("="*50 + "\n\n")
    
    # 返回日志内容
    return log_content


# Streamlit UI
st.title("📢 语音转写 & 拼音比对系统")

# 上传音频
# audio_file = st.file_uploader("上传音频文件 (MP3 格式)", type=["mp3"])
# 允许上传的所有音频格式
ALLOWED_FORMATS = ["mp3", "wav", "m4a", "flac", "aac", "ogg", "wma", "amr", "opus"]
audio_file = st.file_uploader("上传音频文件", type=ALLOWED_FORMATS)
correct_text = st.text_area("请输入正确文本:")

if st.button("开始分析"):
    if audio_file and correct_text:
        # 保存上传的音频
        temp_audio_path = f"temp_{audio_file.name}"
        with open(temp_audio_path, "wb") as f:
            f.write(audio_file.read())
        
        # 转换为 WAV 格式（如果不是 WAV）
        if not temp_audio_path.endswith(".wav"):
            st.info("正在转换音频文件为 WAV 格式...")
            temp_audio_path = convert_audio(temp_audio_path, "wav")
            st.success("转换完成！")

        st.info("正在生成纠错报告...")
        
        correct_text = unify_punctuation(correct_text)
        transcribed_text = transcribe_audio(temp_audio_path)
        transcribed_text = unify_punctuation(transcribed_text )
            
        correct_pinyin = text_to_pinyin(correct_text)
        transcribed_pinyin = text_to_pinyin(transcribed_text)

        # 生成纠错报告
        correction_report = generate_correction_report(correct_text, transcribed_text, correct_pinyin, transcribed_pinyin)

        # 记录日志
        log_content = log_transcription(correct_text, correct_pinyin, transcribed_text, transcribed_pinyin, correction_report, audio_file.name)

        st.success("生成完成！")

        # 显示结果
#        st.subheader("✅ 正确文本")
 #       st.write(correct_text)

#        st.subheader("🔄 识别文本")
#        st.write(transcribed_text)

#        st.subheader("📖 识别拼音")
#        st.write(transcribed_pinyin)

        st.subheader("📌 纠错报告")
        st.markdown(correction_report, unsafe_allow_html=True)

        # 下载日志
        st.download_button("📥 下载反馈报告", log_content, file_name="transcription_log.txt", mime="text/plain")

    else:
        st.warning("请上传音频文件并输入正确文本！")

# 查看历史日志
if st.button("📜 查看历史日志"):
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, "r", encoding="utf-8") as log:
            st.text_area("历史日志", log.read(), height=300)
    else:
        st.info("暂无日志记录。")