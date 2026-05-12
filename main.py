from PySide6.QtWidgets import (QApplication, QWidget, QGridLayout, QLabel, QLineEdit, QComboBox, QPushButton, QProgressBar,
                                QListWidget, QListWidgetItem, QScrollArea, QFileDialog, QPlainTextEdit)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import QThreadPool, QRunnable, QObject, Signal, QTimer
from multiprocessing import Process
from re import findall, compile, MULTILINE
from time import time
from ast import literal_eval
import os, zipfile, sys

is_main = __name__ == "__main__"

### Search function: FOR MULTIPROCESSING WORKERS ###
def search(query, subset, id_num):
    result_bytes = findall(query, subset)

    results = [result for result in result_bytes]
    
    with open(f"result_tempfiles/results{id_num}.txt", 'w') as results_file:
        results_file.write(str(results))

    results = None

### MAIN PROCESS ###
if is_main:

    ### If required, set up data ###

    # Create the data folder
    if not os.path.isdir('data'):
        os.mkdir('data')
    
    # Creates the result_tempfiles folder
    if not os.path.isdir('result_tempfiles'):
        os.mkdir('result_tempfiles')

    # Creates the default newline character
    if not os.path.isfile('data/newline_char.txt'):
        with open('data/newline_char.txt', 'w') as newline_char:
            print("Using default newline character\n")
            newline_char.write('|')

    # Extract the metadata .csv file in the data folder
    if not os.path.isfile('data/gutenberg_metadata.csv') and os.path.isfile('archive.zip'):
        print('Unzipping, please wait...')
        with zipfile.ZipFile("archive.zip", 'r') as zipped_archive:
            zipped_archive.extract('gutenberg_metadata.csv', 'data')
        print('Extracted .csv file\n')
    elif not os.path.isfile('data/gutenberg_metadata.csv') and not os.path.isfile('archive.zip'):
        # If there's no data, exit
        print("There is no data. Exiting...")
        sys.exit()

    # Search-optimise the .csv file
    if not os.path.isfile('data/gutenberg_metadata_optimised.csv'):
        from re import sub
        print("Search-optimising the data...")

        # Split file by newlines
        with open('data/gutenberg_metadata.csv', encoding="utf-8") as the_file:
            total_lines = len(the_file.read().split('\n'))
        
        # Capture headings, write to a seperate file
        with open('data/gutenberg_metadata.csv', encoding="utf-8") as the_file:
            columns = the_file.read().split('\n')[0].strip()

            columns = sub("(no images, older E-readers)", "(no images; older E-readers)", columns)
            columns = ",".join([heading.strip().strip('"') for heading in columns.split(",")])

            headings = open('data/gutenberg_metadata_headings.csv', 'w', encoding='utf-8')
            headings.write(columns)
            headings.close()

            print("Headings noted, .csv generated\n")


        with open('data/gutenberg_metadata.csv', encoding="utf-8") as csv_file:
            lines = []
            current_line_num = 0
            the_file = csv_file.read()

            with open('data/gutenberg_metadata_headings.csv') as heads:
                headings = heads.read().split(',')
            
            newline_char = open("data/newline_char.txt",'r').read().strip()

            # Replace all newlines with the newline char
            for line in the_file.split("\n")[1:]:
                line_split = line.split(',')
                first_piece = (line_split[0])
                valid_first_piece = not (False in [(x in '1234567890') for x in first_piece])
                try:
                    valid_second_piece = line_split[1].strip() in ['Text', 'Dataset', 'Sound', 'Image', 'MovingImage']
                except IndexError:
                    valid_second_piece = False
                
                if valid_first_piece and valid_second_piece and len(line_split) >= len(headings):
                    lines.append(line.strip())
                elif len(line_split) > 1:
                    if valid_first_piece and valid_second_piece:
                        lines.append(line.strip())
                    else:
                        lines[-1] += (newline_char+line.strip())
                else:
                    lines[-1] += (newline_char+line.strip())
                
                current_line_num += 1
                if current_line_num == total_lines or current_line_num % 10000 == 0:
                    print(f"Completed line {current_line_num}/{total_lines}")

        with open('data/gutenberg_metadata_optimised.csv', 'w', encoding='utf-8') as new_file:
            new_file.write("\n".join(lines))

        print("Complete.\nSearch-optmised .csv generated\n")


    ### MAIN ONLY: Init values ###

    CSV_PATH = "data/gutenberg_metadata_optimised.csv"

    with open('data/newline_char.txt', 'r') as char:
        newline_char = char.read()

    with open('data/gutenberg_metadata_headings.csv') as heads:
        headings = heads.read().split(',')

    with open(CSV_PATH, "rb") as data:
        total_lines = sum(1 for _ in data)

    search_result_windows = []
    book_detail_windows = []
    ereader_windows = []

    ### MAIN ONLY: PiSide6 Init ###
    app = QApplication(sys.argv)
    main_window = QWidget()
    main_window.setWindowTitle('Incunabula Library')

    threadpool = QThreadPool()
    prefered_search_threads = threadpool.maxThreadCount() - 1
    max_search_threads = prefered_search_threads if threadpool.maxThreadCount()-1 >= prefered_search_threads else (threadpool.maxThreadCount()-1 if threadpool.maxThreadCount()-1 > 0 else 1)
    print(f"{max_search_threads} threads available for searching")

    logo = QPixmap("logo.png")

    print('...')

    ### MAIN ONLY: main process exclusive logic ###
    # This is invoked when the user clicks the window's Search button.

    start_time = 0

    def start_search():
        global search_bar, search_topic, search_button, total_lines, start_time, max_search_threads, CSV_PATH, threadpool, disclaimer_label

        start_time = time()

        disclaimer_label.hide()
        progress_bar.setValue(0)
        progress_bar.show()
        search_bar.setEnabled(False)
        search_topic.setEnabled(False)
        search_button.setEnabled(False)
        
        query = search_bar.text()
        query_mode = search_topic.currentText()[:-1]
        print(f'Searching "{query}" in mode "{query_mode}"')

        match query_mode:
            case 'All':
                re_query_str = f'^.*{query}.*$'
            case "Etext Number":
                re_query_str = f'^{query},.*$'
            case "Issued":
                re_query_str = f'^[0-9]+,[A-Za-z]+,[^,]*{query}[^,]*,.*$'
            case "Title":
                re_query_str = f'[0-9]+,[A-Za-z]+,[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9],(?:".*{query}.*"|[^,]*{query}[^,]*),.*$'
            case "LoCC":
                re_query_str = f'[0-9]+,[A-Za-z]+,[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9],(?:".*"|[^,]*),(?:".*{query}.*"|[^,]*{query}[^,]*),.*$'
            case "Bookshelves":
                re_query_str = f'[0-9]+,[A-Za-z]+,[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9],(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*{query}.*"|[^,]*{query}[^,]*),.*$'
            case "Authors":
                re_query_str = f'[0-9]+,[A-Za-z]+,[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9],(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*{query}.*"|[^,]*{query}[^,]*),.*$'
            case "Subjects":
                re_query_str = f'[0-9]+,[A-Za-z]+,[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9],(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*"|[^,]*),(?:".*{query}.*"|[^,]*{query}[^,]*),.*$'
        
        re_query_compiled = compile(re_query_str.encode('utf-8'), MULTILINE)

        with open(CSV_PATH, 'rb') as data:
            dataset = data.read().split(b'\n')
        
        subdivides = [0]
        chunk_size = round((total_lines + 1) / max_search_threads)

        for chunk in range(0, max_search_threads):
            subdivides.append(subdivides[-1] + chunk_size)
        
        subdivides[-1] = total_lines + 1

        subsets = []
        for chunk_num in range(0,max_search_threads):
            subset = b"\n".join(dataset[subdivides[chunk_num]:subdivides[chunk_num+1]])
            subsets.append(subset)

        searcher = thread_runner(re_query_compiled, subsets)
        searcher.signal.finished.connect(finish_search)
        searcher.signal.update.connect(update_progress_bar)
        threadpool.start(searcher)
        
        data = None
        dataset = None
        subsets = None

    # For communicating back to the main thread from the worker runner.
    class search_signal(QObject):
        finished = Signal(list)
        update = Signal(int)

    class thread_runner(QRunnable):
        # Runs the search processes and emits progress events.
        def __init__(self, query, subsets):
            super().__init__()
            self.setAutoDelete(True)
            self.signal = search_signal()
            self.subsets = subsets
            self.query = query
        
        def run(self):
            global max_search_threads
            processes = []
            count = 0

            for subset in self.subsets:
                process = Process(target=search, args=(self.query, subset, count,))
                processes.append(process)
                count += 1

            for process in processes:
                process.start()

            finished_search = False
            finished_count = 0
            while not finished_search:
                is_alive_set = [process.is_alive() for process in processes]
                finished_search = not (True in is_alive_set)
                if finished_count != is_alive_set.count(False):
                    finished_count = is_alive_set.count(False)
                    self.signal.update.emit(finished_count)
            
            final_results = []
            for result_count in range(0, max_search_threads):
                with open(f'result_tempfiles/results{result_count}.txt', 'r') as result_file:
                    result = literal_eval(result_file.read())
                    result = [item.decode('utf-8') for item in result]
                    final_results += result
                os.remove(f'result_tempfiles/results{result_count}.txt')

            result = None

            self.signal.finished.emit(final_results)
            final_results = []

            self.signal.deleteLater()

    def update_progress_bar(counter):
        # Update the progress bar using the number of finished subprocesses.
        global progress_bar, max_search_threads

        progress_bar.setValue(round(counter/max_search_threads*100))

    def finish_search(results):
        # Handle completed search results and restore the main UI.
        global search_bar, search_topic, search_button, start_time

        print(f"Search completed of {total_lines} records in {time() - start_time} sec")
        print(f"{len(results)} results found")

        original_query = search_bar.text()
        original_mode = search_topic.currentText()[:-1]

        run_search_results(results, original_query, original_mode)
        
        progress_bar.hide()
        disclaimer_label.show()
        search_bar.clear()
        search_bar.setEnabled(True)
        search_topic.setEnabled(True)
        search_button.setEnabled(True)

        print("Search is now available again\n...")
    
    ### Diplay listings ###
    def run_search_results(results, query, mode, stylesheet=None):
        global search_result_windows

        if stylesheet:
            search_result = search_results(results, query, mode, stylesheet)
        else:
            search_result = search_results(results, query, mode)
        
        search_result_windows.append(search_result)
        search_result_windows[-1].show()

    class search_results(QWidget):
        # Window showing a list of matched book records.
        def __init__(self, results = [], query='', mode='', styleSheet = None):
            global headings
            super().__init__(styleSheet=styleSheet)
            self.setMinimumSize(500,500)
            self.layout = QGridLayout()

            print("Generating results window...")

            self.results = []
            temp_results = results
            for result in temp_results:
                if result.strip() == '':
                    continue

                split_result = result.split(',')
                datapoints = []

                for count in range(0,len(split_result)):
                    if "|PASS-OVER|" in split_result[count]:
                        continue
                    if len(split_result[count]) == 0:
                        datapoints.append('')
                        continue
                    if split_result[count][0] == '"':
                        another_count = 0
                        while split_result[count+another_count][-1] != '"':
                            another_count += 1
                            split_result[count] += ","+split_result[count+another_count]
                            split_result[count+another_count] = "|PASS-OVER|"+split_result[count+another_count][-1]
                        
                        split_result[count] = split_result[count][1:-1]
                    datapoints.append(split_result[count])
                
                dictionary_points = {}
                for num in range(0,len(headings)):
                    dictionary_points[headings[num]] = datapoints[num]
                self.results.append(dictionary_points)

            self.query = query
            self.mode = mode

            self.generate()
        
        def generate(self):
            global headings
            self.setWindowTitle(f'Incunabula Library - "{self.mode}:{self.query}"')

            self.list = QListWidget()
            self.list.itemClicked.connect(open_book_detail)

            for result in self.results:
                self.list.addItem(enhanced_list_item_widget(result))
            
            self.layout.addWidget(self.list,0,0)
            
            self.setLayout(self.layout)
        

    def open_book_detail(item, stylesheet=None):
        # Open a detailed view for the selected search result.
        global book_detail_windows
        selected_book = item.record

        if stylesheet:
            search_result = book_details(selected_book, stylesheet)
        else:
            search_result = book_details(selected_book)
        
        book_detail_windows.append(search_result)
        book_detail_windows[-1].show()

    class enhanced_list_item_widget(QListWidgetItem):
        def __init__(self, /, record):
            global headings
            super().__init__()
            self.record = record
            self.setText((headings[0]+ ': ' +self.record[headings[0]] +' - '+ self.record['Title']+" by " + self.record['Authors']) if self.record['Authors'] != "" else (headings[0]+ ': ' +self.record[headings[0]] +' - '+ self.record['Title']))

    class book_details(QWidget):
        # Display metadata and actions for a single book.
        def __init__(self, book, styleSheet = None):
            global headings
            super().__init__(styleSheet=styleSheet)
            self.layout = QGridLayout()


            self.book = book
            self.ID = book[headings[0]]

            self.generate()
        
        def generate(self):
            global headings
            self.setWindowTitle(f'Incunabula Library - ID:{self.ID}~{self.book['Title']}')

            labels = []
            for heading in headings:
                text = self.book[heading]
                make_link = False

                if heading in headings[10:-1] and text != '':
                    text = f'''<a href="{text.strip()}">{text.strip()}</a>'''
                    make_link = True
                if heading == "Other Links" and text != '':
                    text = "\n".join([f'''<a href="{link.strip()}">{link.strip()}</a>''' for link in text.split(';')])
                    make_link = True
                if text == '':
                    text = "Not available :("
                
                if '\n' not in text:
                    new_label = QLabel(text)
                    if make_link:
                        new_label.setOpenExternalLinks(True)
                    
                    labels.append(new_label)
                else:
                    for link in text.split('\n'):
                        new_label = QLabel(link)
                        new_label.setOpenExternalLinks(True)
                        labels.append(new_label)
            
            counter = 0
            subset_widget = QWidget()
            subset_layout = QGridLayout()

            for label in labels:
                subset_layout.addWidget(QLabel(headings[counter] if counter < len(headings) else ""), counter, 0, 1, 1)
                subset_layout.addWidget(label, counter, 1, 1, 3)
                counter += 1
            
            subset_widget.setLayout(subset_layout)

            subset_scroll_area = QScrollArea()
            subset_scroll_area.setWidget(subset_widget)
            
            read_button = QPushButton("Read locally in plain text")
            read_button.clicked.connect(self.read_book)

            extract_button = QPushButton("Extract plain text version to folder")
            extract_button.clicked.connect(self.extract_book)


            self.layout.addWidget(subset_scroll_area, 0, 0, 4, 4)
            self.layout.addWidget(extract_button, 5, 0, 1, 2)
            self.layout.addWidget(read_button, 5, 2, 1, 2)


            self.setLayout(self.layout)
    

        def read_book(self, stylesheet):
            global book_detail_windows
            selected_book = self.ID
            selected_title = self.book['Title']

            if stylesheet:
                reading_book = book_reader(selected_book, selected_title, stylesheet)
            else:
                reading_book = book_reader(selected_book, selected_title)
            
            ereader_windows.append(reading_book)
            ereader_windows[-1].show()
            print(f'"{selected_title}" has been opened\n...')

        def extract_book(self):
            
            extract_location = QFileDialog()
            extract_location.setFileMode(QFileDialog.FileMode.Directory)

            extract_location.exec()

            extracted_location = extract_location.selectedFiles()[0]
            
            with zipfile.ZipFile("archive.zip", 'r') as archive:
                with archive.open(f'books/{self.ID}', 'r') as book:
                    book_text = book.read().decode('utf-8')
                    with open(extracted_location+"/"+self.book['Title']+'.txt', 'w', encoding='utf-8') as extracted_book:
                        extracted_book.write(book_text)
                        extracted_book.flush()
                        book_text = None
            
            print(f'"{self.book['Title']}" has been extracted to "{extracted_location}"\n...')

    class book_reader(QWidget):
        # Load and display the full text of a selected book from the archive.
        def __init__(self, bookID, bookTitle, styleSheet = None):
            global headings
            super().__init__(styleSheet=styleSheet)
            self.setMinimumSize(750,500)
            self.layout = QGridLayout()


            self.bookID = bookID
            self.bookTitle = bookTitle

            with zipfile.ZipFile("archive.zip", 'r') as archive:
                with archive.open(f'books/{self.bookID}', 'r') as book:
                    self.book_text = book.read().decode('utf-8')

            self.generate()
        
        def generate(self):
            self.setWindowTitle(f'Incunabula Library - ID:{self.bookID}~{self.bookTitle}')

            book = QPlainTextEdit(self.book_text)
            book.setReadOnly(True)
            self.layout.addWidget(book, 0, 0)
            self.setLayout(self.layout)
    
    # Periodically destroys hidden windows to free memory.
    def clear_dead_widgets():
        global search_result_windows, book_detail_windows, ereader_windows
        for num in range(0,len(search_result_windows)):
            widget = search_result_windows[num]
            if not widget.isVisible():
                widget.destroy()
                search_result_windows[num] = "DESTROYED"
        while "DESTROYED" in search_result_windows: search_result_windows.remove("DESTROYED");

        for num in range(0,len(book_detail_windows)):
            widget = book_detail_windows[num]
            if not widget.isVisible():
                widget.destroy()
                book_detail_windows[num] = "DESTROYED"
        while "DESTROYED" in book_detail_windows: book_detail_windows.remove("DESTROYED");

        for num in range(0,len(ereader_windows)):
            widget = ereader_windows[num]
            if not widget.isVisible():
                widget.destroy()
                ereader_windows[num] = "DESTROYED"
        while "DESTROYED" in ereader_windows: ereader_windows.remove("DESTROYED");


    ### MAIN ONLY: Home Screen Layout ###
    home_label = QLabel(pixmap=logo)

    search_bar = QLineEdit()
    search_bar.setPlaceholderText("Search...")

    search_topic = QComboBox()
    search_topics = ['Title', 'Authors', 'Subjects', 'Etext Number', 'LoCC', 'Issued', 'Bookshelves', 'All']
    search_topic.addItems([heading+':' for heading in search_topics])

    search_button = QPushButton("Search")
    search_button.clicked.connect(start_search)

    disclaimer_label = QLabel("Note: Search is case sensitive, and exact match")

    progress_bar = QProgressBar()
    progress_bar.setRange(0,100)
    progress_bar.hide()

    main_layout = QGridLayout()
    main_layout.addWidget(home_label, 0, 0, 1, 5)
    main_layout.addWidget(search_topic, 1, 0)
    main_layout.addWidget(search_bar, 1, 1, 1, 3)
    main_layout.addWidget(search_button, 1, 4, 1, 1)
    main_layout.addWidget(progress_bar,2,1,1,3)
    main_layout.addWidget(disclaimer_label,2,1,1,3)

    ### MAIN ONLY: Apply layout ###
    main_window.setLayout(main_layout)

    ### MAIN ONLY: Setup the cleaner ###
    cleaner = QTimer()
    cleaner.timeout.connect(clear_dead_widgets)
    cleaner.setInterval(5000)
    cleaner.start()

    ### MAIN ONLY: Show and run ###
    main_window.show()
    sys.exit(app.exec())