import os
import shutil
from pathlib import Path
from utils import screenRelocation

# 你的已有函数：screenRelocation（无需修改，此处仅作占位提示，确保你已提前定义该函数）
# 函数功能：package_name（目标文件夹路径）、current_screenshot（给定图片路径），返回最相似图片名称
# def screenRelocation(package_name, current_screenshot):
#     你的原有实现逻辑
#     return most_similar_image_name

def process_appdata_folders(root_dir: str):
    """
    主处理函数：遍历appData下所有文件夹，基于自定义相似度函数完成图片对比与替换
    目录结构：root_dir / 子文件夹 / (上层jpg图片 + smartback子文件夹)
    smartback结构：smartback / (xxx.jpg + xxx.json) 成对存在
    """
    # 验证根目录存在
    root_path = Path(root_dir)
    if not root_path.exists():
        raise FileNotFoundError(f"根目录不存在：{root_dir}")

    # 遍历appData下的所有子文件夹
    n = 0
    for sub_folder in root_path.iterdir():
        if not sub_folder.is_dir():
            continue  # 跳过文件，只处理文件夹

        # 定义smartback子文件夹路径
        smartback_folder = sub_folder / "smartback"
        if not smartback_folder.exists():
            print(f"跳过文件夹 {sub_folder.name}：未找到smartback子文件夹")
            continue

        # 定义上层文件夹路径（即sub_folder，作为screenRelocation的package_name参数）
        upper_folder_path = str(sub_folder)

        # 验证上层文件夹是否有jpg图片（提前过滤，避免无效调用）
        upper_jpg_exists = any(
            file.is_file() and file.suffix.lower() == ".jpg" and file.parent != smartback_folder
            for file in sub_folder.iterdir()
        )
        if not upper_jpg_exists:
            print(f"文件夹 {sub_folder.name}：上层无jpg图片可对比")
            continue

        # 收集smartback中的所有jpg图片路径
        smartback_jpg_paths = []
        for file in smartback_folder.iterdir():
            if file.is_file() and file.suffix.lower() == ".jpg":
                smartback_jpg_paths.append(str(file))

        if not smartback_jpg_paths:
            print(f"文件夹 {sub_folder.name} 的smartback：无jpg图片可处理")
            continue

        # 处理每张smartback中的jpg图片
        for smart_jpg_path in smartback_jpg_paths:
            smart_jpg_path_obj = Path(smart_jpg_path)
            # 获取smartback中jpg的文件名（含后缀，用于保留原命名格式；不含后缀用于重命名）
            smart_jpg_basename = smart_jpg_path_obj.stem
            smart_jpg_ext = smart_jpg_path_obj.suffix.lower()

            try:
                # 1. 调用你的自定义相似度函数，获取上层文件夹中最相似的图片名称
                # package_name：上层文件夹路径 | current_screenshot：smartback中的jpg图片路径
                most_similar_upper_jpg_number,similarity = screenRelocation(upper_folder_path, smart_jpg_path)
                most_similar_upper_jpg_name = str(most_similar_upper_jpg_number) + "_screenshot.jpg"
                # 验证返回的图片名称有效
                if not most_similar_upper_jpg_name:
                    print(f"跳过 {smart_jpg_path_obj.name}：未找到相似图片")
                    continue

                # 拼接最相似图片的完整路径（上层文件夹 + 返回的图片名称）
                most_similar_upper_jpg_path = sub_folder / most_similar_upper_jpg_name
                if not most_similar_upper_jpg_path.exists():
                    print(f"跳过 {smart_jpg_path_obj.name}：找到的相似图片 {most_similar_upper_jpg_name} 不存在")
                    continue

                # 2. 定义目标路径：smartback中，以当前smart jpg的名称命名（替换原文件）
                target_jpg_path = smart_jpg_path_obj.parent / f"{smart_jpg_basename}{smart_jpg_ext}"

                # 3. 先删除原smartback中的jpg图片（避免覆盖失败）
                if target_jpg_path.exists():
                    target_jpg_path.unlink()

                # 4. 复制最相似的上层图片到目标路径，完成重命名与替换
                shutil.copy2(str(most_similar_upper_jpg_path), str(target_jpg_path))
                n = n+1
                print(f"处理文件数量: {n}")
                print(f"成功处理：{smart_jpg_path_obj.name} -> 替换为 {most_similar_upper_jpg_name}（重命名为 {target_jpg_path.name}）")
            except Exception as e:
                print(f"处理 {smart_jpg_path_obj.name} 失败：{str(e)}")
                continue

    print("\n所有文件夹处理完成！")

if __name__ == "__main__":
    # 配置：请替换为你的appData文件夹实际路径
    APP_DATA_ROOT_DIR = "static/appData"  # Windows示例路径
    # APP_DATA_ROOT_DIR = "/Users/你的用户名/Library/Application Support"  # Mac示例路径
    try:
        # 确保你已在运行前定义好 screenRelocation 函数
        process_appdata_folders(APP_DATA_ROOT_DIR)
    except Exception as e:
        print(f"程序异常终止：{str(e)}")