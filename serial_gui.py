import tkinter as tk
from tkinter import scrolledtext
import serial
import serial.tools.list_ports
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import matplotlib.pyplot as plt
import threading
import time
import queue
import numpy as np

class SerialApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Serial Communication with Graph")

        # Initialize serial port and communication state
        self.serial_port = None
        self.is_open = False
        self.data_thread = None
        self.data_running = False
        self.detect_scheduled = False

        # Queue for data communication between threads
        self.data_queue = queue.Queue()

        # Create the PanedWindow
        self.paned_window = tk.PanedWindow(root, orient=tk.HORIZONTAL)
        self.paned_window.pack(fill=tk.BOTH, expand=True)

        # Create the left pane for menu buttons and debugging information
        self.left_pane = tk.Frame(self.paned_window, width=500)
        self.left_pane.pack_propagate(False)  # Prevent the frame from resizing
        self.paned_window.add(self.left_pane)

        # Create the right pane for graph
        self.right_pane = tk.Frame(self.paned_window)
        self.paned_window.add(self.right_pane)

        # Create the debugging information window and place it at the bottom of the left pane
        self.debugging_text = scrolledtext.ScrolledText(self.left_pane, height=10, wrap=tk.WORD)
        self.debugging_text.pack(side=tk.BOTTOM, fill=tk.BOTH, padx=5, pady=5)

        # Create the main frame for menu buttons
        self.main_frame = tk.Frame(self.left_pane)
        self.main_frame.pack(pady=10, padx=10, fill=tk.BOTH, expand=True)

        # Port selection label and dropdown menu
        self.port_label = tk.Label(self.main_frame, text="Select Serial Port:")
        self.port_label.grid(row=0, column=0, padx=5, pady=5)
        
        self.port_var = tk.StringVar()
        self.port_menu = tk.OptionMenu(self.main_frame, self.port_var, *self.get_serial_ports())
        self.port_menu.grid(row=0, column=1, padx=5, pady=5)

        # Baud rate selection label and entry
        self.baud_label = tk.Label(self.main_frame, text="Baud Rate:")
        self.baud_label.grid(row=1, column=0, padx=5, pady=5)
        
        self.baud_entry = tk.Entry(self.main_frame)
        self.baud_entry.insert(0, "115200")  # Default baud rate
        self.baud_entry.grid(row=1, column=1, padx=5, pady=5)

        # Start and close buttons
        self.start_button = tk.Button(self.main_frame, text="Start", command=self.start_serial)
        self.start_button.grid(row=2, column=0, padx=5, pady=5)
        
        self.close_button = tk.Button(self.main_frame, text="Close", command=self.close_serial)
        self.close_button.grid(row=2, column=1, padx=5, pady=5)

        # Status label
        self.status_label = tk.Label(self.main_frame, text="Status: Not Connected")
        self.status_label.grid(row=3, column=0, columnspan=2, padx=5, pady=5)

        # Create a check button to control graph drawing
        self.draw_graph_var = tk.BooleanVar(value=True)  # Default is True (checked)
        self.draw_graph_checkbutton = tk.Checkbutton(self.main_frame, text="Draw 2D & 3D Graphs", variable=self.draw_graph_var)
        self.draw_graph_checkbutton.grid(row=4, column=0, columnspan=2, padx=5, pady=5)

        # Current distance label with large font size
        self.distance_label = tk.Label(self.main_frame, text="Current Distance: -- mm", font=("Helvetica", 36))
        self.distance_label.grid(row=5, column=0, columnspan=2, padx=5, pady=5)

        # Set up the Matplotlib figure, axes, and 3D subplot
        self.fig = plt.figure(figsize=(12, 6))
        self.ax1 = self.fig.add_subplot(121)  # 2D plot
        self.ax1.set_title("Real-time Millimeter Data")
        self.ax1.set_xlabel("Time")
        self.ax1.set_ylabel("Distance (mm)")

        # Create a 3D subplot to the right
        self.ax2 = self.fig.add_subplot(122, projection='3d')  # 3D plot
        self.ax2.set_title("Distance Data in 3D")

        # Remove axis labels
        self.ax2.set_xlabel('')
        self.ax2.set_ylabel('')
        self.ax2.set_zlabel('')

        # Initialize the 3D line plot
        self.line_3d, = self.ax2.plot([0, 0], [0, 0], [0, 0], label='Distance Line')

        # Set axis limits
        self.ax2.set_xlim(-1, 1)  # Adjust if necessary
        self.ax2.set_ylim(0, 1)
        self.ax2.set_zlim(-1, 1)  # Adjust if necessary

        # Draw a rectangle in front of the lines
        self.draw_rectangle()

        # Canvas for matplotlib figure
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.right_pane)
        self.canvas.get_tk_widget().pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.data = []
        self.time_data = []  # Time data for plotting

    def create_sphere(self, radius, center):
        """ Create the vertices of a sphere. """
        u = np.linspace(0, 2 * np.pi, 100)
        v = np.linspace(0, np.pi, 100)
        u, v = np.meshgrid(u, v)
        x = center[0] + radius * np.sin(v) * np.cos(u)
        y = center[1] + radius * np.sin(v) * np.sin(u)
        z = center[2] + radius * np.cos(v)
        return x, y, z        

    def draw_rectangle(self):
        """ Draw a rectangle in front of the lines in the 3D plot. """
        x = np.array([-0.5, 0.5, 0.5, -0.5])
        y = np.array([0, 0, 1, 1])
        z = np.array([0, 0, 0, 0])
        self.ax2.plot(x, y, z, color='b')  # Bottom rectangle
        self.ax2.plot(x, y, [1, 1, 1, 1], color='b')  # Top rectangle
        self.ax2.plot([x[0], x[0]], [y[0], y[0]], [0, 1], color='b')  # Vertical lines
        self.ax2.plot([x[1], x[1]], [y[1], y[1]], [0, 1], color='b')
        self.ax2.plot([x[2], x[2]], [y[2], y[2]], [0, 1], color='b')
        self.ax2.plot([x[3], x[3]], [y[3], y[3]], [0, 1], color='b')

    def get_serial_ports(self):
        """ Get a list of available serial ports. """
        ports = serial.tools.list_ports.comports()
        return [port.device for port in ports]

    def start_serial(self):
        """ Start serial communication. """
        port = self.port_var.get()
        baud_rate = self.baud_entry.get()
        
        if port and baud_rate:
            try:
                self.serial_port = serial.Serial(port, baud_rate, timeout=1)
                self.is_open = True
                self.status_label.config(text=f"Status: Connected to {port} at {baud_rate} baud")
                self.data_running = True
                self.data_thread = threading.Thread(target=self.read_serial_data)
                self.data_thread.start()
                
                if not self.detect_scheduled:
                    self.schedule_initial_detect()  # Start scheduling detect after opening the port
                
            except Exception as e:
                tk.messagebox.showerror("Error", f"Failed to open serial port: {e}")
        else:
            tk.messagebox.showwarning("Input Error", "Please select a port and enter a baud rate.")

    def read_serial_data(self):
        """ Continuously read serial data and put it into the queue. """
        while self.data_running:
            try:
                if self.serial_port.in_waiting > 0:
                    # Read data from serial port
                    data = self.serial_port.read(8)
                    if data[1] == 0x07:
                        status = data[2]
                        distance = data[3] * 65536 + data[4] * 256 + data[5]
                        message = f"Status:{status}\tDistance:{distance} mm\n"
                        self.debugging_text.insert(tk.END, message)
                        self.debugging_text.see(tk.END)  # Scroll to the end of the text widget

                        self.data_queue.put(distance)
      
                time.sleep(0.01)
            except Exception as e:
                self.debugging_text.insert(tk.END, f"Error in serial read: {e}\n")
                break

    def mm_to_inches(self, mm):
        return mm / 25.4        

    def update_plot(self):
        """ Update the graph with the latest data from the queue. """
        if not self.data_queue.empty():
            while not self.data_queue.empty():
                distance = self.data_queue.get()
                self.data.append(distance)
                self.time_data.append(len(self.data))

                # Update the distance label
                #self.distance_label.config(text=f"Current Distance:\n{distance} mm")

                 # Convert distance to inches
                distance_in_inches = self.mm_to_inches(distance)
                self.distance_label.config(text=f"Current Distance:\n{distance} mm\n({distance_in_inches:.2f} inches)")

            # Draw the 2D and 3D graphs only if the check button is checked
            if self.draw_graph_var.get():
                # Update 2D plot
                x_data = range(len(self.data))
                y_data = self.data
                self.ax1.clear()
                self.ax1.plot(x_data, y_data, 'r-')
                self.ax1.set_title("Real-time Millimeter Data")
                self.ax1.set_xlabel("Time")
                self.ax1.set_ylabel("Distance (mm)")
                self.ax1.set_xlim(0, len(self.data))
                if self.data:
                    self.ax1.set_ylim(min(self.data) - 10, max(self.data) + 10)

                # Update 3D plot (line length changes based on current distance)
                x_data_3d = [0, 0]
                y_data_3d = [0, distance]  # Line length is based on current distance
                z_data_3d = [0, 0]  # Constant z-axis

                self.line_3d.set_data(x_data_3d, y_data_3d)
                self.line_3d.set_3d_properties(z_data_3d)
                self.ax2.set_xlim(-1, 1)  # Adjust if necessary
                self.ax2.set_ylim(0, max(self.data) + 10)
                self.ax2.set_zlim(-1, 1)  # Adjust if necessary

                # Remove previous spheres (if any)
                if hasattr(self, 'sphere'):
                    self.sphere.remove()

                # Create a new sphere at the end of the line
                radius = 0.05  # Adjust the radius as needed
                center = (0, distance, 0)
                x, y, z = self.create_sphere(radius, center)
                self.sphere = self.ax2.plot_surface(x, y, z, color='r', alpha=0.6)

                # Remove tick marks on x and y axes
                self.ax2.set_xticks([])
                self.ax2.set_zticks([])

                self.canvas.draw()


    def update_plot_periodically(self):
        """ Periodically check the queue and update the plot. """
        self.update_plot()
        self.root.after(100, self.update_plot_periodically)  # Adjust interval as needed

    def close_serial(self):
        """ Close the serial port if it's open. """
        if self.is_open and self.serial_port:
            self.data_running = False
            self.data_thread.join()
            self.serial_port.close()
            self.is_open = False
            self.detect_scheduled = False
            self.status_label.config(text="Status: Not Connected")
            self.debugging_text.insert(tk.END, "Serial port closed.\n")

    def start_detect(self):
        """ Send a command to start measurement. """
        if self.serial_port and self.is_open:
            key = 0x05
            value = [0, 0, 0, 0]
            cmd = self.create_cmd(key, value)
            self.serial_port.flush()
            self.serial_port.write(bytearray(cmd))

    def stop_detect(self):
        """ Send a command to stop measurement. """
        if self.serial_port and self.is_open:
            key = 0x06
            value = [0, 0, 0, 0]
            cmd = self.create_cmd(key, value)
            self.serial_port.flush()
            self.serial_port.write(bytearray(cmd))

    def set_detect_mod(self):
        """ Send a command to set detect mode. """
        if self.serial_port and self.is_open:
            key = 0x0D
            value = [0, 0, 0, 0x01]
            cmd = self.create_cmd(key, value)
            self.serial_port.flush()
            self.serial_port.write(bytearray(cmd))

    def schedule_initial_detect(self):
        """ Schedule initial detection sequence. """
        if self.is_open:
            self.stop_detect()
            self.root.after(100, self.set_detect_mod)  # Wait 100ms and then set detect mode
            self.root.after(200, self.schedule_start_detect)  # Schedule start_detect at 200ms total delay

    def schedule_start_detect(self):
        """ Start detection at 20ms intervals. """
        if self.is_open:
            self.start_detect()
            self.root.after(20, self.schedule_start_detect)  # Repeat every 20ms

    def crc_high_first(self, key, value):
        """ Calculate CRC with high-first method. """
        crc = 0x00  # Initial CRC value

        data = [key, value[0], value[1], value[2], value[3]]

        ptr = 0
        length = len(data)

        while length > 0:
            crc ^= data[ptr]  # XOR with the current data byte
            ptr += 1
            length -= 1
            for _ in range(8):  # Perform the CRC calculation for each bit
                if crc & 0x80:
                    crc = (crc << 1) ^ 0x31
                else:
                    crc = (crc << 1)
            crc &= 0xFF  # Ensure crc is within 8-bit range

        return crc

    def create_cmd(self, key, value):
        """ Create a command with CRC. """
        cmd = [0] * 8  # Initialize a list of 8 elements
        cmd[0] = 0x55  # Head
        cmd[1] = key  # Key
        cmd[2] = value[0]  # Value
        cmd[3] = value[1]  # Value
        cmd[4] = value[2]  # Value
        cmd[5] = value[3]  # Value
        cmd[6] = self.crc_high_first(key, value)  # CRC
        cmd[7] = 0xAA  # End

        return cmd

if __name__ == "__main__":
    root = tk.Tk()
    app = SerialApp(root)
    root.after(100, app.update_plot_periodically)  # Start periodic plot updates
    root.mainloop()
