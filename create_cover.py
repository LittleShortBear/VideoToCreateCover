import cv2
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import sys
import os
import tkinter as tk
from tkinter import colorchooser, messagebox, filedialog, ttk
import re # 用于处理HEX颜色字符串

# 1. 确定运行时的基础路径，并确保它是 pathlib.Path 对象
if getattr(sys, 'frozen', False):
    # 如果是打包后的exe (pyinstaller/auto-py-to-exe)，使用 sys._MEIPASS
    # 必须将其强制转换为 Path 对象！
    base_path = Path(sys._MEIPASS) 
else:
    # 否则使用脚本当前目录
    base_path = Path(__file__).resolve().parent

# 2. 连接路径：使用 / 运算符连接 Path 对象和字符串
# 注意：这要求你在 auto-py-to-exe 中将 DENGB.TTF 打包到 _internal 目录下
DEFAULT_FONT_PATH = str(base_path  / "DENGB.TTF")

# DEFAULT_FONT_PATH = str(Path("GetVideoCover\DENGB.TTF").resolve())
# DEFAULT_FONT_PATH = str(Path("_internal\DENGB.TTF").resolve())

# ==============================================================================
# 核心处理函数 (Core Processing Functions)
# ==============================================================================

def extract_frame_from_video(video_path, seek_time_sec=None):
    """从视频中提取一帧。"""
    # 保持不变
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        return None
    if seek_time_sec is not None:
        cap.set(cv2.CAP_PROP_POS_MSEC, seek_time_sec * 1000)
    else:
        cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        return None
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(frame_rgb)

# --- [修正后的换行函数]：移除标点，并智能换行 ---
def wrap_text_by_segment_and_character(text, font, max_width):
    """
    根据标点符号分割文字组，并移除标点符号。
    优先放入整组（无标点），放不下则进行字符级换行。

    :param text: 完整的字符串。
    :param font: Pillow ImageFont 对象。
    :param max_width: 允许的最大像素宽度。
    :return: 一个包含多行字符串的列表。
    """
    # 匹配中文和英文常用标点符号，并使用非捕获模式来丢弃它们
    PUNCTUATION_PATTERN = r'[,\.!\?:;"\'，。？！；：“”‘’【】（）\(\)]+'
    
    # 1. 使用 re.split() 分割文本。标点符号被用作分隔符并被丢弃。
    parts = re.split(PUNCTUATION_PATTERN, text)
    
    # 2. 过滤掉分割后可能产生的空字符串，并对每个片段去除首尾空格
    # parts 现在只包含纯净的文本片段
    parts = [p.strip() for p in parts if p.strip()]

    lines = []
    current_line = ""

    for part in parts:
        # 3. 尝试将整个 part (片段) 加入当前行
        
        # 3.1 预处理：如果当前行非空，我们在添加新片段前应加入一个空格，以分隔两个逻辑组
        separator = " " if current_line else ""
        
        test_segment = separator + part
        test_line = current_line + test_segment
        
        try:
            line_width = font.getlength(test_line)
        except AttributeError:
             line_width = font.getsize(test_line)[0]

        if line_width <= max_width:
            # 3.2 成功：整个 part (带分隔符) 放入当前行
            current_line = test_line
        else:
            # 3.3 失败：整个 part 太长，或加入后超出限制
            
            # --- 场景 A: 当前行已有内容，但新片段放不下 ---
            if current_line:
                lines.append(current_line)
                current_line = "" # 重置行

            # --- 场景 B: 对太长的 part (片段) 进行字符级分割 ---
            # 分割时不需要考虑 separator，因为 current_line 已经被重置
            temp_line = ""
            
            for char in part:
                test_temp_line = temp_line + char
                
                try:
                    char_line_width = font.getlength(test_temp_line)
                except AttributeError:
                    char_line_width = font.getsize(test_temp_line)[0]
                    
                if char_line_width <= max_width:
                    temp_line = test_temp_line
                else:
                    lines.append(temp_line)
                    temp_line = char # 新行以这个字符开始
            
            # 4. 将 part 分割后的最后一行设置为新的 current_line
            # 这样下一轮循环就可以继续在这一行后面添加文字
            current_line = temp_line

    # 5. 别忘了添加最后一行
    if current_line:
        lines.append(current_line)
        
    # 清理所有行首尾的空格，特别是行首的 group separator
    return [line.strip() for line in lines]


def add_title_to_image(image, title_text, font_path, font_size, text_color_rgb, stroke_color_rgb, stroke_offset, padding_ratio):
    """
    在图像上居中添加（可自动换行的）标题文字，并应用用户定义的颜色、描边和边距。
    """
    draw = ImageDraw.Draw(image)

    # 1. 加载字体
    try:
        font = ImageFont.truetype(font_path, font_size)
    except IOError:
        raise FileNotFoundError(f"无法加载字体文件：{font_path}")

    # 2. 定义边界和最大宽度 (使用传入的 padding_ratio)
    img_width, img_height = image.size
    
    # 根据比例计算内边距
    padding_x = int(img_width * padding_ratio)
    padding_x = max(10, padding_x) # 确保至少有 10px 的边距
    max_text_width = img_width - (padding_x * 2)

    # 3. 换行
    print(f"正在处理文字: {title_text}")
    wrapped_lines = wrap_text_by_segment_and_character(title_text, font, max_text_width)
    
    if not wrapped_lines:
        return image

    # 4. 计算文字块的总高度
    try:
        _, line_top, _, line_bottom = font.getbbox("A_g")
        line_height = line_bottom - line_top
    except AttributeError:
        line_height = font.getsize("A")[1]
    
    line_spacing = int(line_height * 0.2)
    total_text_height = (len(wrapped_lines) * line_height) + (max(0, len(wrapped_lines) - 1) * line_spacing)

    # 5. 计算起始Y坐标（垂直居中）
    current_y = (img_height - total_text_height) / 2

    # 6. 循环绘制每一行
    for line in wrapped_lines:
        # 计算每行的X坐标（水平居中）
        try:
            line_width = font.getlength(line)
        except AttributeError:
            line_width = font.getsize(line)[0]
            
        x = (img_width - line_width) / 2

        # 绘制描边/阴影
        offset = stroke_offset
        for dx in [-offset, 0, offset]:
            for dy in [-offset, 0, offset]:
                if dx != 0 or dy != 0: 
                    draw.text((x + dx, current_y + dy), line, font=font, fill=stroke_color_rgb)

        # 绘制主要文字
        draw.text((x, current_y), line, font=font, fill=text_color_rgb)
        
        # 移动到下一行
        current_y += line_height + line_spacing

    return image

# ==============================================================================
# GUI 逻辑 (GUI Logic)
# ==============================================================================

class ConfigApp:
    def __init__(self, master):
        self.master = master
        master.title("封面图片生成器配置")
        master.resizable(False, False)

        # --- 默认值 ---
        self.default_font_color = (233, 212, 0) 
        self.default_stroke_color = (0, 0, 0)  

        # --- 配置变量 ---
        self.folder_path = tk.StringVar(value=r"D:\my_videos")

        # 如果默认字体存在，就用它；否则，设置一个常用的默认值
        initial_font_path = DEFAULT_FONT_PATH if Path(DEFAULT_FONT_PATH).exists() else "simhei.ttf"
        self.font_path = tk.StringVar(value=initial_font_path)
        
        self.font_size = tk.IntVar(value=100)
        self.stroke_offset = tk.IntVar(value=3)
        self.seek_time = tk.DoubleVar(value=1.0)
        self.text_color = tk.StringVar(value=self._rgb_to_hex(self.default_font_color))
        self.stroke_color = tk.StringVar(value=self._rgb_to_hex(self.default_stroke_color))
        # [新增] 左右边距比例，0.05 = 5% 边距，0.5 = 50% 边距
        self.padding_ratio = tk.DoubleVar(value=0.05) 
        
        # --- 创建界面 ---
        self._create_widgets()

    def _rgb_to_hex(self, rgb):
        """将 RGB 元组转换为 HEX 字符串"""
        return f'#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}'

    def _hex_to_rgb(self, hex_color):
        """将 HEX 字符串转换为 RGB 元组"""
        hex_color = hex_color.lstrip('#')
        # 检查是否是有效的6位HEX
        if re.fullmatch(r'[0-9a-fA-F]{6}', hex_color):
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        # 如果是RGB格式的字符串，尝试解析 (例如 "233,212,0")
        try:
            return tuple(map(int, hex_color.split(',')))
        except ValueError:
             messagebox.showerror("颜色格式错误", f"输入的颜色格式 '{hex_color}' 无效。将使用默认颜色。")
             return self.default_font_color
             
    def _create_widgets(self):
        # 框架
        main_frame = ttk.Frame(self.master, padding="10")
        main_frame.pack(fill='both', expand=True)

        # 视频文件夹路径
        ttk.Label(main_frame, text="视频文件夹路径:").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(main_frame, textvariable=self.folder_path, width=40).grid(row=0, column=1, pady=5)
        ttk.Button(main_frame, text="浏览", command=self._browse_folder).grid(row=0, column=2, padx=5)

        # 字体文件路径
        ttk.Label(main_frame, text="字体文件路径:").grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(main_frame, textvariable=self.font_path, width=40).grid(row=1, column=1, pady=5)
        ttk.Button(main_frame, text="浏览", command=self._browse_font).grid(row=1, column=2, padx=5)

        # --- 字体设置区域 ---
        setting_frame = ttk.LabelFrame(main_frame, text="字体与描边设置", padding="10")
        setting_frame.grid(row=2, column=0, columnspan=3, sticky='ew', pady=10)

        # 1. 字体大小
        ttk.Label(setting_frame, text="字体大小 (px):").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(setting_frame, textvariable=self.font_size, width=10).grid(row=0, column=1, sticky='w', padx=10)

        # 2. 描边偏移量
        ttk.Label(setting_frame, text="描边偏移量 (px):").grid(row=1, column=0, sticky='w', pady=5)
        ttk.Entry(setting_frame, textvariable=self.stroke_offset, width=10).grid(row=1, column=1, sticky='w', padx=10)
        
        # 3. 字体颜色
        ttk.Label(setting_frame, text="字体颜色 (HEX/R,G,B):").grid(row=0, column=2, sticky='w', pady=5, padx=(20, 0))
        ttk.Entry(setting_frame, textvariable=self.text_color, width=15).grid(row=0, column=3, sticky='w')
        self.text_color_button = ttk.Button(setting_frame, text="选择颜色", command=lambda: self._choose_color(self.text_color, self.text_color_button))
        self.text_color_button.grid(row=0, column=4, padx=5)
        self._update_color_button(self.text_color.get(), self.text_color_button)

        # 4. 描边颜色
        ttk.Label(setting_frame, text="描边颜色 (HEX/R,G,B):").grid(row=1, column=2, sticky='w', pady=5, padx=(20, 0))
        ttk.Entry(setting_frame, textvariable=self.stroke_color, width=15).grid(row=1, column=3, sticky='w')
        self.stroke_color_button = ttk.Button(setting_frame, text="选择颜色", command=lambda: self._choose_color(self.stroke_color, self.stroke_color_button))
        self.stroke_color_button.grid(row=1, column=4, padx=5)
        self._update_color_button(self.stroke_color.get(), self.stroke_color_button)
        
        # --- 额外设置区域 ---
        extra_frame = ttk.LabelFrame(main_frame, text="额外设置", padding="10")
        extra_frame.grid(row=3, column=0, columnspan=3, sticky='ew', pady=10)
        
        # 5. 视频截取时间
        ttk.Label(extra_frame, text="获取视频时间 (秒):").grid(row=0, column=0, sticky='w', pady=5)
        ttk.Entry(extra_frame, textvariable=self.seek_time, width=10).grid(row=0, column=1, sticky='w', padx=10)
        
        # [新增] 6. 左右边距比例
        ttk.Label(extra_frame, text="左右边距比例 (0.05=小边距):").grid(row=0, column=2, sticky='w', pady=5, padx=(20, 0))
        ttk.Entry(extra_frame, textvariable=self.padding_ratio, width=10).grid(row=0, column=3, sticky='w')
        
        # 7. 执行按钮
        ttk.Button(main_frame, text="开始生成封面", command=self._run_main_process).grid(row=4, column=0, columnspan=3, pady=20)


    def _browse_folder(self):
        folder = filedialog.askdirectory(title="选择视频文件夹")
        if folder:
            self.folder_path.set(folder)

    def _browse_font(self):
        """弹出文件选择框，如果没有选择则保持原有路径（即默认路径）。"""
        current_path = Path(self.font_path.get()).parent if Path(self.font_path.get()).exists() else "."
        
        font_file = filedialog.askopenfilename(
            title="选择字体文件", 
            initialdir=current_path,
            filetypes=[("字体文件", "*.ttf;*.otf;*.ttc")]
        )
        
        if font_file:
            self.font_path.set(font_file)

    def _update_color_button(self, hex_or_rgb_str, button):
        """更新按钮的背景色以显示当前选中的颜色"""
        try:
            rgb = self._hex_to_rgb(hex_or_rgb_str)
            hex_color = self._rgb_to_hex(rgb)
            button.config(style=f"C.{hex_color}.TButton")
            self.master.style.configure(f"C.{hex_color}.TButton", background=hex_color)
        except Exception:
            pass

    def _choose_color(self, color_var, button):
        color_code = colorchooser.askcolor(title="选择颜色")
        if color_code:
            hex_color = color_code[1]
            color_var.set(hex_color)
            self._update_color_button(hex_color, button)


    def _run_main_process(self):
        """从GUI获取数据并调用主处理逻辑"""
        try:
            config = {
                "VIDEO_FOLDER_PATH": self.folder_path.get(),
                "FONT_FILE_PATH": self.font_path.get(),
                "FONT_SIZE": self.font_size.get(),
                "STROKE_OFFSET": self.stroke_offset.get(),
                "SEEK_TIME_SECONDS": self.seek_time.get(),
                "TEXT_COLOR_RGB": self._hex_to_rgb(self.text_color.get()),
                "STROKE_COLOR_RGB": self._hex_to_rgb(self.stroke_color.get()),
                "PADDING_RATIO": self.padding_ratio.get(), # [新增]
            }

            process_videos(config)
            
            messagebox.showinfo("执行成功", "所有视频封面已成功生成！\n请检查您的视频文件夹。")

        except Exception as e:
            messagebox.showerror("执行失败", f"生成过程出现严重错误：\n{e}")

def process_videos(config):
    """
    接收配置字典，执行批量视频处理。
    """
    # 提取配置
    VIDEO_FOLDER_PATH = config["VIDEO_FOLDER_PATH"]
    FONT_FILE_PATH = config["FONT_FILE_PATH"]
    FONT_SIZE = config["FONT_SIZE"]
    STROKE_OFFSET = config["STROKE_OFFSET"]
    SEEK_TIME_SECONDS = config["SEEK_TIME_SECONDS"]
    TEXT_COLOR_RGB = config["TEXT_COLOR_RGB"]
    STROKE_COLOR_RGB = config["STROKE_COLOR_RGB"]
    PADDING_RATIO = config["PADDING_RATIO"] # [新增]
    
    VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv')

    # 路径验证
    video_folder = Path(VIDEO_FOLDER_PATH)
    font_path_obj = Path(FONT_FILE_PATH)
    
    if not video_folder.is_dir():
        raise FileNotFoundError(f"视频文件夹未找到：{VIDEO_FOLDER_PATH}")
    if not font_path_obj.exists():
        raise FileNotFoundError(f"字体文件未找到：{FONT_FILE_PATH}")

    # 开始遍历
    processed_count = 0
    failed_videos = []
    
    for file_path_obj in video_folder.glob('*'):
        
        if file_path_obj.suffix.lower() in VIDEO_EXTENSIONS:
            
            video_title = file_path_obj.stem
            output_cover_path = file_path_obj.with_suffix('.jpg')

            try:
                # 提取帧
                frame_image = extract_frame_from_video(str(file_path_obj), seek_time_sec=SEEK_TIME_SECONDS)
                if frame_image is None:
                    raise Exception("无法提取帧")

                # 添加标题
                image_with_title = add_title_to_image(
                    image=frame_image,
                    title_text=video_title,
                    font_path=FONT_FILE_PATH,
                    font_size=FONT_SIZE,
                    text_color_rgb=TEXT_COLOR_RGB,
                    stroke_color_rgb=STROKE_COLOR_RGB,
                    stroke_offset=STROKE_OFFSET,
                    padding_ratio=PADDING_RATIO # [新增] 传递内边距比例
                )
                if image_with_title is None:
                    raise Exception("无法添加文字（可能字体文件损坏或配置错误）")

                # 保存
                image_with_title.save(output_cover_path, "JPEG", quality=95)
                processed_count += 1
                print(f"成功: {output_cover_path.name}")
                
            except Exception as e:
                failed_videos.append((file_path_obj.name, str(e)))
                print(f"失败: {file_path_obj.name} -> {e}")

    # 如果有失败，抛出汇总的错误
    if failed_videos:
        error_msg = f"部分或全部文件处理失败 ({len(failed_videos)}/{processed_count + len(failed_videos)}):\n"
        for name, reason in failed_videos:
            error_msg += f"- {name}: {reason}\n"
        raise Exception(error_msg)


# ==============================================================================
# 脚本入口点
# ==============================================================================
if __name__ == "__main__":
    root = tk.Tk()
    root.style = ttk.Style()
    
    app = ConfigApp(root)
    
    root.mainloop()