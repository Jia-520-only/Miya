import os


class FileUtil:
    @staticmethod
    def get_child_file_paths(directory):
        child_file_paths = []
        if not os.path.exists(directory):
            return child_file_paths
        for root, dirs, files in os.walk(directory):
            for file in files:
                child_file_paths.append(os.path.join(root, file))
        return child_file_paths

    @staticmethod
    def get_subfolder_names(path):
        subfolder_names = []
        if not os.path.exists(path):
            return subfolder_names
        for root, dirs, files in os.walk(path):
            for file in files:
                subfolder_names.append(file.replace(".mp4", ""))
        return subfolder_names
