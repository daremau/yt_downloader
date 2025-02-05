import tkinter
import customtkinter
from pytubefix import YouTube

def download():
    try:
        yt_link = link.get()
        yt_object = YouTube(yt_link, on_progress_callback=on_progress)

        video = yt_object.streams.get_highest_resolution()
        video.download()
    
    except Exception as e:
        finish_label.configure(text=f"Error downloading video: {e}", text_color="red")

def on_progress(stream, chunk, bytes_remaining):
    total_size = stream.filesize
    bytes_downloaded = total_size - bytes_remaining
    pct_completion = str(int(bytes_downloaded / total_size * 100))
    percentage.configure(text=f"{pct_completion} %")
    percentage.update()

    progress_bar.set(float(pct_completion) / 100)
        

#System Settings
customtkinter.set_appearance_mode("System")
customtkinter.set_default_color_theme("blue")

#App frame
app = customtkinter.CTk()
app.geometry("720x480")
app.title("Youtube Downloader")

#UI Elements
title = customtkinter.CTkLabel(app, text="Insert a youtube link")
title.pack(padx=10, pady=10)

url = tkinter.StringVar()
link = customtkinter.CTkEntry(app, width=350, height=40, textvariable=url)
link.pack()

finish_label = customtkinter.CTkLabel(app, text="")
finish_label.pack()

#Progress bar
percentage = customtkinter.CTkLabel(app, text="0%")
percentage.pack()

progress_bar = customtkinter.CTkProgressBar(app, width=400)
progress_bar.set(0)
progress_bar.pack(padx=10, pady=10)


download = customtkinter.CTkButton(app, text="Download", command=download)
download.pack(padx=10, pady=10)

app.mainloop()