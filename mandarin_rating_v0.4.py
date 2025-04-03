from pydub import AudioSegment
import subprocess
import os
from pypinyin import pinyin
import gradio as gr
from termcolor import colored
import subprocess
import re
import argparse

LOG_FILE = "transcription_log.txt"  # 记录文件


import markdown
from markdown.extensions.tables import TableExtension

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
    
    # 4. 错误拼音所在的词语，以及该词语的正确拼音和中文释义。
    # 5. 对每个错误进行详细的改正建议，并且提供一个简洁的总结，指出朗读中主要的问题。

    # ### **【正确拼音】**
    # {correct_pinyin}

    # ### **【转写文本】**
    # {transcribed_text}

    #（当且仅当【正确文本】和【转写文本】也对不上的时候才判定为错误，例如"jǐn""jìn"对应的可能都是文字"尽"）

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
    1. **将【正确文本】转写为拼音，并与【转写拼音】作比对**，找出所有错误，并根据评分标准扣分，提供详细的纠错说明，包括：
    - 1) 错误拼音对应的正确拼音，及其对应的正确文本。
    - 2) 错误类型（如：声母错误、韵母错误、声调错误、拼音缺失、重复拼音等）。
    - 3) 发音时的注意要点，说明如何避免此类错误。
    2. **返回最终得分（满分 100）**，并解释扣分原因。  
    3. **必须以 HTML 表格格式返回，确保在 HTML 界面中正确显示**。  
    4. **如果完全正确，返回 `<p>🎉 朗读完全正确，得分：100/100</p>`**。

    ---

    ### **【正确文本】**
    # {correct_text}

    ### **【转写拼音】**
    {transcribed_pinyin}

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
    
    with open(LOG_FILE, "a", encoding="utf-8") as log:
        log.write(f"音频文件: {audio_file}\n")
        log.write(f"正确文本: {correct_text}\n")
        log.write(f"正确拼音: {' '.join(correct_pinyin)}\n")
        log.write(f"识别文本: {transcribed_text}\n")
        log.write(f"识别拼音: {transcribed_pinyin}\n")
        log.write(f"纠错报告:\n{correction_report}\n")
        # log.write(f"拼音比对结果: {comparison_result}\n")
        # log.write(f"正确率: {correct_rate:.2f}%\n")
        log.write("="*50 + "\n\n")

def process_files(correct_text, audio_file):
    transcribed_text = transcribe_audio(audio_file)

    # 去掉时间戳
    cleaned_transcription = remove_timestamps(transcribed_text)
    
    correct_pinyin = text_to_pinyin(correct_text)
    transcribed_pinyin = text_to_pinyin(cleaned_transcription )
    transcribed_pinyin = " ".join(transcribed_pinyin)

    # # 比对拼音并标红错误部分，同时返回标红后的正确文本
    # correct_text_result, transcribed_pinyin_result = compare_pinyin(
    #     correct_pinyin, transcribed_pinyin, correct_text
    # )

    correction_report = generate_correction_report(correct_text, cleaned_transcription, correct_pinyin, transcribed_pinyin)

    # 写入日志
    # log_transcription(correct_text_result, correct_pinyin, transcribed_text, transcribed_pinyin_result, correction_report, audio_file)
    log_transcription(correct_text, correct_pinyin, cleaned_transcription, transcribed_pinyin, correction_report, audio_file)

    # **在返回的 HTML 结果中加入标题**
    correct_text_html = f"<h3>正确文本</h3>{correct_text}"
    transcribed_pinyin_html = f"<h3>识别拼音</h3>{transcribed_pinyin}"
    correction_report_html = f"<h3>纠错报告</h3>{correction_report}"

    return correct_text_html, transcribed_pinyin_html, correction_report_html
    # return correction_report_html

def view_log():
    if not os.path.exists(LOG_FILE):
        return "暂无记录。"
    with open(LOG_FILE, "r", encoding="utf-8") as log:
        return log.read()
    
def main():
    parser = argparse.ArgumentParser(description="音频转写和拼音比对工具")
    parser.add_argument("correct_text", help="正确的文本")
    parser.add_argument("audio_file", help="上传的音频文件路径")

    args = parser.parse_args()

    correct_text = args.correct_text
    audio_file = args.audio_file

    correct_text_result, transcribed_pinyin_result, correction_report_result = process_files(correct_text, audio_file)
    
    print(f"正确文本: {correct_text_result}")
    print(f"识别拼音: {transcribed_pinyin_result}")
    print(f"纠错报告: {correction_report_result}")

if __name__ == "__main__":
    main()