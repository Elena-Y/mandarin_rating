# mandarin_rating
项目背景：基于中高级汉语口语课程作业，开发一个面向国际中文教育领域的留学生汉语口语自动评分系统。

项目进度：
- v0.1（Mar 14）：调用whisper API实现音频转写，调用pypinyin实现拼音转写，调用gradio编写用户可交互页面。
- v0.2（Mar 20）：模型改用whisper-cli（有时间戳+有标点），用红色标明正确拼音和转写拼音的不一致之处，加上在线和本地记录。
- v0.3（Mar 28）：调用deepseek-chat编写纠错报告，基于2024秋试卷制定评分标准。
- v0.4（Apr 2）：命令行输入。
- v0.5（Apr 3）：用户界面改用streamlit（由于服务器无法运行gradio.Audio），优化prompt使输出标准化。
