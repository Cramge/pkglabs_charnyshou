"""View: widgets and rendering only. Color state belongs to ColorController."""
import tkinter as tk
import customtkinter as ctk
from PIL import Image, ImageDraw, ImageTk
from color_models import SPECS
from controller import ColorController

ACCENT, INK = '#635BFF', '#17233D'

def pixel(rgb, outside=False, hatch=False):
    return tuple(round(255*(.65*v+.35 if outside and hatch else v)) for v in rgb)

class GradientSlider(tk.Canvas):
    """A real gradient track with mouse dragging and keyboard navigation."""
    def __init__(self, parent, lo, hi, command):
        super().__init__(parent, height=28, width=256, bg='white', highlightthickness=1,
                         highlightbackground='white', highlightcolor=ACCENT, takefocus=True, cursor='hand2')
        self.lo, self.hi, self.command = lo, hi, command
        self.value, self.samples, self.photo = lo, [], None
        self.bind('<Button-1>', self.drag)
        self.bind('<B1-Motion>', self.drag)
        self.bind('<Configure>', lambda e: self.redraw())
        for key, direction in (('Left', -1), ('Down', -1), ('Right', 1), ('Up', 1)):
            self.bind('<'+key+'>', lambda e, d=direction: self.step(d))
        self.bind('<Home>', lambda e: self.command(self.lo))
        self.bind('<End>', lambda e: self.command(self.hi))

    def drag(self, event):
        self.focus_set()
        fraction = max(0, min(1, (event.x-6)/max(1, self.winfo_width()-12)))
        self.command(self.lo+fraction*(self.hi-self.lo))

    def step(self, direction):
        self.command(max(self.lo, min(self.hi, self.value+direction*(self.hi-self.lo)/255)))
        return 'break'

    def set(self, value):
        self.value = value
        self.draw_marker()

    def set_samples(self, samples):
        self.samples = samples
        self.redraw()

    def redraw(self):
        if not self.samples:
            return
        image = Image.new('RGB', (len(self.samples), 14))
        image.putdata([pixel(rgb, outside, (x+y)%7 == 0) for y in range(14)
                       for x, (rgb, outside) in enumerate(self.samples)])
        image = image.resize((max(1, self.winfo_width()-12), 16), Image.Resampling.BILINEAR)
        self.photo = ImageTk.PhotoImage(image, master=self)
        self.delete('track')
        self.create_image(6, 6, image=self.photo, anchor='nw', tags='track')
        self.draw_marker()

    def draw_marker(self):
        self.delete('marker')
        x = 6+(self.value-self.lo)/(self.hi-self.lo)*max(1, self.winfo_width()-12)
        self.create_rectangle(x-3, 3, x+3, 25, fill='', outline=INK, width=3, tags='marker')
        self.create_line(x, 4, x, 24, fill='white', width=2, tags='marker')

class ColorPalette(tk.Canvas):
    def __init__(self, parent):
        super().__init__(parent,width=256,height=round(112*parent._get_widget_scaling()),
                         highlightthickness=0,cursor='crosshair',bg='white')
        self.samples, self.position, self.photo = [], (0,0), None
        self.bind('<Configure>',lambda e:self.redraw())

    def set_samples(self,samples,position):
        self.samples,self.position = samples,position
        self.redraw()

    def redraw(self):
        if not self.samples:
            return
        image = Image.new('RGB',(64,28))
        image.putdata([pixel(rgb,outside,(i%64+i//64)%6==0) for i,(rgb,outside) in enumerate(self.samples)])
        width,height = max(1,self.winfo_width()),max(1,self.winfo_height())
        image = image.resize((width,height),Image.Resampling.BILINEAR)
        x,y = self.position[0]*(width-1),self.position[1]*(height-1)
        draw = ImageDraw.Draw(image)
        draw.ellipse((x-5,y-5,x+5,y+5),outline=INK,width=3)
        draw.ellipse((x-4,y-4,x+4,y+4),outline='white',width=1)
        self.photo = ImageTk.PhotoImage(image,master=self)
        self.delete('all')
        self.create_image(0,0,image=self.photo,anchor='nw')

class ColorLab(ctk.CTk):
    def __init__(self):
        ctk.set_appearance_mode('light')
        super().__init__()
        self.controller = ColorController()
        self.title('ColorLab • CMYK ↔ LAB ↔ RGB')
        self.geometry('1120x810')
        self.minsize(1030, 650)
        self.configure(fg_color='#F3F5FA')
        self.entries, self.sliders, self.palettes = {}, {}, {}
        self.pending, self.palette_job, self.matrix_window = None, None, None
        body = ctk.CTkScrollableFrame(self, fg_color='transparent')
        body.pack(fill='both', expand=True, padx=20, pady=12)
        ctk.CTkLabel(body, text='ColorLab', font=('Segoe UI', 30, 'bold'), text_color=INK).pack(anchor='w')
        settings = ctk.CTkFrame(body, fg_color='white')
        settings.pack(fill='x', pady=(4, 12))
        self.illuminant = self.option(settings, 'Освещение', ['D65', 'D50', 'E'])
        self.separation = self.option(settings, 'Цветоделение', ['GCR', 'UCR'])
        self.gamut = self.option(settings, 'Вне охвата', ['Clipping', 'Scaling'])
        ctk.CTkButton(settings, text='Матрицы', width=100, command=self.show_matrices).pack(side='right', padx=12)
        self.settings_hint = ctk.CTkLabel(body, text='', anchor='w', justify='left', wraplength=1020, text_color='#69768D')
        self.settings_hint.pack(fill='x', pady=(0, 8))
        preview = ctk.CTkFrame(body, fg_color='white', corner_radius=16)
        preview.pack(fill='x', pady=(0, 14))
        self.swatch = ctk.CTkLabel(preview, text='', width=80, height=64, corner_radius=12)
        self.swatch.pack(side='left', padx=16, pady=12)
        self.hex_label = ctk.CTkLabel(preview, text='', font=('Consolas', 26, 'bold'), text_color=INK)
        self.hex_label.pack(side='left')
        ctk.CTkButton(preview, text='Сброс', width=85, command=lambda: self.update_color('RGB', (79,69,230))).pack(side='right', padx=16)
        ctk.CTkButton(preview, text='Копировать HEX', fg_color=ACCENT, command=self.copy_hex).pack(side='right')
        cards = ctk.CTkFrame(body, fg_color='transparent')
        cards.pack(fill='x')
        for column, model in enumerate(SPECS):
            cards.grid_columnconfigure(column, weight=1, uniform='panel')
            self.make_panel(cards, model, column)
        self.status = ctk.CTkLabel(body, text='', wraplength=1000, anchor='w', justify='left', height=55)
        self.status.pack(fill='x', pady=(12, 4))
        ctk.CTkLabel(body, text='Enter — применить ввод · Стрелки — менять ползунок · Home/End — границы\nCMYK — учебная модель красок без ICC-профиля.',
                     text_color='#69768D', justify='left', anchor='w').pack(fill='x')
        self.render()

    def option(self, parent, title, options):
        group = ctk.CTkFrame(parent, fg_color='transparent')
        group.pack(side='left', padx=12, pady=10)
        ctk.CTkLabel(group, text=title).pack(side='left', padx=(0,8))
        result = ctk.CTkOptionMenu(group, values=options, width=106, command=lambda v: self.change_settings())
        result.pack(side='left')
        return result

    def make_panel(self, parent, model, column):
        panel = ctk.CTkFrame(parent, fg_color='white', corner_radius=16)
        panel.grid(row=0, column=column, sticky='nsew', padx=5)
        panel.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(panel, text=model, font=('Segoe UI',23,'bold'), text_color=INK).grid(row=0,column=0,sticky='w',padx=18,pady=12)
        self.entries[model], self.sliders[model] = [], []
        for i, (name, lo, hi) in enumerate(SPECS[model]):
            row = ctk.CTkFrame(panel, fg_color='transparent')
            row.grid(row=1+i*2, column=0, sticky='ew', padx=18)
            ctk.CTkLabel(row, text=f'{name}   [{lo}…{hi}]', anchor='w').pack(side='left')
            entry = ctk.CTkEntry(row, width=95, height=28, justify='right')
            entry.pack(side='right')
            entry.bind('<Return>', lambda e,m=model: self.read_fields(m))
            entry.bind('<FocusOut>', lambda e,m=model: self.read_fields(m))
            entry.bind('<KeyRelease>', lambda e,m=model: self.queue_input(m,e))
            slider = GradientSlider(panel,lo,hi,lambda v,m=model,j=i: self.change_component(m,j,v))
            slider.grid(row=2+i*2,column=0,sticky='ew',padx=18,pady=(2,7))
            self.entries[model].append(entry)
            self.sliders[model].append(slider)
        if model != 'CMYK':
            ctk.CTkFrame(panel,height=65,fg_color='transparent').grid(row=7,rowspan=2,column=0)
        axes = {'CMYK':'C → / M ↑ · Y, K фиксированы', 'LAB':'a* → / b* ↑ · L* фиксирована', 'RGB':'R → / G ↑ · B фиксирована'}
        ctk.CTkLabel(panel,text=axes[model],text_color='#69768D',font=('Segoe UI',12)).grid(row=9,column=0,padx=18,sticky='w')
        palette = ColorPalette(panel)
        palette.grid(row=10,column=0,padx=18,pady=(4,18),sticky='ew')
        palette.bind('<Button-1>',lambda e,m=model:self.pick(m,e))
        palette.bind('<B1-Motion>',lambda e,m=model:self.pick(m,e))
        self.palettes[model] = palette

    def cancel_input(self):
        if self.pending:
            self.after_cancel(self.pending)
            self.pending = None

    def queue_input(self,model,event):
        if event.keysym not in ('Return','Tab','Shift_L','Shift_R'):
            self.cancel_input()
            self.pending = self.after(450,lambda:self.read_fields(model))

    def read_fields(self,model):
        self.cancel_input()
        if self.controller.read_fields(model,[e.get() for e in self.entries[model]]):
            self.render()
        else:
            self.render_status()

    def update_color(self,model,values):
        self.cancel_input()
        self.controller.update(model,values)
        self.render()

    def change_component(self,model,index,value):
        self.cancel_input()
        self.controller.change_component(model,index,value)
        self.render()

    def pick(self,model,event):
        self.cancel_input()
        self.controller.pick(model,event.x/max(1,event.widget.winfo_width()-1),event.y/max(1,event.widget.winfo_height()-1))
        self.render()

    def change_settings(self):
        self.cancel_input()
        self.controller.settings(self.illuminant.get(),self.separation.get(),self.gamut.get())
        self.render()

    def render_status(self):
        self.status.configure(text=self.controller.message,text_color='#A65A08' if self.controller.warning else '#69768D')

    def render(self):
        c = self.controller
        for model in SPECS:
            for entry,slider,value in zip(self.entries[model],self.sliders[model],c.values[model]):
                text = f'{value:.3f}'
                if entry.get() != text:
                    entry.delete(0,'end')
                    entry.insert(0,text)
                slider.set(value)
        self.hex_label.configure(text=c.hex)
        self.swatch.configure(fg_color=c.hex)
        light = {'D65':'средний дневной свет','D50':'тёплый дневной свет','E':'равноэнергетический источник'}[c.engine.illuminant]
        mode = 'замена серой компоненты во всём диапазоне' if c.engine.separation == 'GCR' else 'удаление подложечного цвета в глубоких тенях'
        self.settings_hint.configure(text=f'{c.engine.illuminant} — {light}. {c.engine.separation} — {mode}.\nПри смене освещения сохраняется цвет sRGB, пересчитываются LAB и матрицы.')
        self.render_status()
        if self.matrix_window and self.matrix_window.winfo_exists():
            self.matrix_box.configure(state='normal')
            self.matrix_box.delete('1.0','end')
            self.matrix_box.insert('1.0',c.matrix_text())
            self.matrix_box.configure(state='disabled')
        # Throttle, do not debounce: gradients continue updating while dragging.
        if not self.palette_job:
            self.palette_job = self.after(30,self.draw_colors)

    def draw_colors(self):
        self.palette_job = None
        c = self.controller
        for model in SPECS:
            for i,slider in enumerate(self.sliders[model]):
                slider.set_samples(c.gradient(model,i))
            samples = c.palette(model)
            ix,iy = c.axes(model)
            def pos(i):
                _,lo,hi = SPECS[model][i]
                return (c.values[model][i]-lo)/(hi-lo)
            self.palettes[model].set_samples(samples,(pos(ix),1-pos(iy)))

    def show_matrices(self):
        if self.matrix_window and self.matrix_window.winfo_exists():
            self.matrix_window.lift()
            return
        self.matrix_window = ctk.CTkToplevel(self)
        self.matrix_window.title('Вычисленные матрицы')
        self.matrix_window.geometry('670x370')
        self.matrix_box = ctk.CTkTextbox(self.matrix_window,font=('Consolas',14))
        self.matrix_box.pack(fill='both',expand=True,padx=16,pady=16)
        self.render()

    def copy_hex(self):
        self.clipboard_clear()
        self.clipboard_append(self.controller.hex)

    def destroy(self):
        self.cancel_input()
        if self.palette_job:
            self.after_cancel(self.palette_job)
            self.palette_job = None
        super().destroy()

if __name__ == '__main__':
    ColorLab().mainloop()
