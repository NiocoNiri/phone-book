"""Телефонная книга. Запуск: python3 phone_book.py

Проверка восстановления: python3 phone_book.py --test
Используются только стандартные библиотеки Python.
"""

# json переводит список словарей в JSON и обратно. JSON — основной формат хранения.
import json
# os нужен для проверки существования, замены и удаления файлов.
import os
# re проверяет телефон и email с помощью регулярных выражений.
import re
# shutil.copy2 создаёт резервную копию файла.
import shutil
# sqlite3 позволяет работать с базой SQLite без установки сторонних библиотек.
import sqlite3
# sys.argv содержит параметры запуска, например --test.
import sys
# tempfile создаёт временную папку для теста, чтобы не затронуть реальные контакты.
import tempfile
# Path помогает составлять пути к файлам и определять папку программы.
from pathlib import Path


# Валидация отделена от добавления: её также используем при чтении файла.
# При неверных данных raise вызывает исключение ValueError; вызывающая функция его обрабатывает.
def validate_contact(name, phone, email, group):
    """Базовые проверки: правила ЛР 23 в задании не приложены."""
    # all требует, чтобы каждое поле было строкой. isinstance проверяет тип значения.
    if not all(isinstance(value, str) for value in (name, phone, email, group)):
        raise ValueError("Все поля контакта должны быть строками.")
    # strip убирает пробелы по краям. Строка из одних пробелов считается пустой.
    if not name.strip():
        raise ValueError("Имя не должно быть пустым.")
    # fullmatch проверяет всю строку: необязательный +, затем от 10 до 15 цифр.
    if not re.fullmatch(r"\+?\d{10,15}", phone.strip()):
        raise ValueError("Телефон: от 10 до 15 цифр, в начале допустим +.")
    # Упрощённая проверка email: текст до @, домен и точка; пробелы запрещены.
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
        raise ValueError("Введите корректный email, например alice@mail.ru.")
    if not group.strip():
        raise ValueError("Группа не должна быть пустой.")


# contacts — общий список словарей. Один словарь описывает один контакт.
# Функция меняет переданный список и возвращает признак успеха True или False.
def add_contact(contacts, name, phone, email, group):
    """Добавить контакт с валидацией. Вернуть True при успехе."""
    try:
        validate_contact(name, phone, email, group)
    except ValueError as error:
        print("Ошибка:", error)
        return False
    # append добавляет словарь в конец списка. Данные пока находятся только в памяти.
    # Запись на диск выполняется отдельно функцией save_contacts из меню.
    contacts.append({"name": name.strip(), "phone": phone.strip(),
                     "email": email.strip(), "group": group.strip()})
    return True


# Поиск возвращает новый список совпадений, исходные контакты не меняются.
def find_contact(contacts, query):
    """Поиск по части имени или телефона без учёта регистра."""
    # casefold приводит текст к виду для сравнения без учёта регистра.
    query = query.strip().casefold()
    # Генератор списка выбирает контакты, где запрос встречается в имени или телефоне.
    # Оператор in проверяет частичное совпадение; пустой запрос найдёт все контакты.
    return [contact for contact in contacts
            if query in contact["name"].casefold() or query in contact["phone"]]


# Удаление сравнивает полное имя без учёта регистра. При одинаковых именах удаляются все.
def delete_contact(contacts, name):
    """Удалить все контакты с указанным полным именем."""
    found = [contact for contact in contacts
             if contact["name"].casefold() == name.strip().casefold()]
    if not found:
        print("Контакт не найден.")
        return False
    # Присваивание срезу [:] меняет содержимое исходного списка.
    # Другие функции, использующие этот же список, увидят удаление.
    contacts[:] = [contact for contact in contacts if contact not in found]
    print("Удалено контактов:", len(found))
    return True


# group=None означает отсутствие фильтра. Если группа указана, выбираем только её.
def list_contacts(contacts, group=None):
    """Вывести все контакты или только выбранную группу."""
    selected = contacts if group is None else [
        contact for contact in contacts
        if contact["group"].casefold() == group.strip().casefold()]
    if not selected:
        print("Контакты не найдены.")
    # enumerate выдаёт номер и контакт; нумерация начинается с 1.
    # f-строка подставляет значения полей в строку для вывода.
    for number, contact in enumerate(selected, 1):
        print(f"{number}. {contact['name']} | {contact['phone']} | "
              f"{contact['email']} | {contact['group']}")


# Проверяем не только синтаксис JSON, но и наличие нужных полей и допустимые значения.
def read_json(filepath):
    """Проверить JSON и структуру данных в нём."""
    # with автоматически закрывает файл. UTF-8 позволяет хранить русские имена.
    with open(filepath, encoding="utf-8") as file:
        # load превращает содержимое JSON-файла в объекты Python.
        contacts = json.load(file)
    if not isinstance(contacts, list):
        raise ValueError("В JSON должен храниться список контактов.")
    for contact in contacts:
        if not isinstance(contact, dict) or not all(
                key in contact for key in ("name", "phone", "email", "group")):
            raise ValueError("Неверная структура контакта.")
        validate_contact(contact["name"], contact["phone"],
                         contact["email"], contact["group"])
    return contacts


# Резервная копия обычно содержит состояние ДО очередного сохранения.
# Функция возвращает False при ошибке, поэтому меню может проверить результат.
def save_contacts(contacts, filepath="contacts.json"):
    """Сохранить JSON; перед записью скопировать исправный файл в .bak."""
    filepath = str(filepath)
    # Сначала пишем в .tmp: ошибка записи не должна испортить основной JSON.
    temporary = filepath + ".tmp"
    try:
        # Повреждённый файл не должен заменять исправную резервную копию.
        if os.path.exists(filepath):
            try:
                # Перед резервным копированием убеждаемся, что старый файл исправен.
                read_json(filepath)
            except (ValueError, UnicodeError):
                print("Предупреждение: повреждённый JSON не копируется в .bak.")
            else:
                # Копируем предыдущую исправную версию в contacts.json.bak.
                shutil.copy2(filepath, filepath + ".bak")
        with open(temporary, "w", encoding="utf-8") as file:
            # dump записывает данные; ensure_ascii=False сохраняет кириллицу читаемой.
            # indent=4 добавляет отступы, чтобы файл было удобно открыть вручную.
            json.dump(contacts, file, ensure_ascii=False, indent=4)
        # Готовый временный файл заменяет основной после успешной записи.
        os.replace(temporary, filepath)
        # При первом сохранении тоже создаём копию для восстановления.
        if not os.path.exists(filepath + ".bak"):
            shutil.copy2(filepath, filepath + ".bak")
        return True
    # OSError — ошибки файловой системы; ValueError/TypeError — ошибки данных.
    except (OSError, ValueError, TypeError) as error:
        print("Ошибка сохранения:", error)
        return False
    # finally выполняется и при успехе, и при ошибке: убираем остаток временного файла.
    finally:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass


# Загрузка вызывается при старте. Разные исключения требуют разных действий.
def load_contacts(filepath="contacts.json"):
    """Если JSON повреждён, загрузить .bak; если отсутствует — пустой список."""
    filepath = str(filepath)
    try:
        return read_json(filepath)
    # Отсутствие файла нормально для первого запуска: создаём пустую книгу.
    except FileNotFoundError:
        print("Файл не найден. Создаётся новая телефонная книга.")
        save_contacts([], filepath)
        return []
    # Невалидный JSON, неверная структура или кодировка: пробуем резервную копию.
    except (ValueError, UnicodeError) as error:
        print("Предупреждение: файл повреждён:", error)
        try:
            # Восстанавливаем список в памяти. На диск его запишет следующее сохранение.
            contacts = read_json(filepath + ".bak")
            print("Контакты восстановлены из .bak.")
            return contacts
        except (OSError, ValueError, UnicodeError) as backup_error:
            print("Не удалось загрузить резервную копию:", backup_error)
            # Не открываем пустую книгу для записи поверх потерянных данных.
            raise RuntimeError("Восстановите файл или резервную копию.") from backup_error
    except OSError as error:
        raise RuntimeError(f"Не удалось прочитать файл: {error}") from error


# SQLite — дополнительный экспорт текущего списка, основная загрузка идёт из JSON.
# База хранится в одном файле contacts.db; отдельный сервер не нужен.
def save_sqlite(contacts, filepath="contacts.db"):
    """Дополнительно сохранить текущие контакты в SQLite."""
    try:
        # connect открывает базу или создаёт её. Контекст with управляет транзакцией:
        # при успехе подтверждает изменения, при исключении откатывает их.
        with sqlite3.connect(filepath) as connection:
            # Создаём таблицу, если её ещё нет. TEXT — строковый тип столбцов.
            # contact_group используется вместо SQL-ключевого слова GROUP.
            connection.execute("""CREATE TABLE IF NOT EXISTS contacts (
                name TEXT, phone TEXT, email TEXT, contact_group TEXT)""")
            # Экспорт заменяет содержимое таблицы текущим списком, исключая дубли.
            connection.execute("DELETE FROM contacts")
            # executemany вставляет несколько строк. Знаки ? — параметры запроса:
            # значения передаются отдельно от SQL, включая имена с кавычками.
            connection.executemany("INSERT INTO contacts VALUES (?, ?, ?, ?)",
                                   [(c["name"], c["phone"], c["email"], c["group"])
                                    for c in contacts])
        print("Контакты сохранены в SQLite:", filepath)
        return True
    except (sqlite3.Error, OSError) as error:
        print("Ошибка SQLite:", error)
        return False


# Автоматическая демонстрация требований задания: пять контактов и восстановление.
# assert останавливает тест с ошибкой, если проверяемое условие не выполнено.
# Запускайте обычным python3 без -O: этот параметр отключает assert.
def run_test():
    """Пять контактов, сохранение, повреждение и восстановление из .bak."""
    # Временная папка удаляется после теста; пользовательские данные не меняются.
    with tempfile.TemporaryDirectory() as folder:
        filepath = Path(folder) / "contacts.json"
        contacts = []
        for number, name in enumerate(["Анна", "Борис", "Вера", "Глеб", "Дарья"]):
            assert add_contact(contacts, name, f"+7916123456{number}",
                               f"contact{number}@mail.ru", "друзья")
        assert save_contacts(contacts, filepath)
        assert load_contacts(filepath) == contacts
        # Намеренно портим JSON, чтобы проверить обработку ошибки и чтение .bak.
        filepath.write_text("{ повреждённый JSON", encoding="utf-8")
        assert load_contacts(filepath) == contacts
        assert save_contacts(contacts, filepath)
        assert load_contacts(filepath) == contacts
        assert len(find_contact(contacts, "ан")) == 1
        assert len(find_contact(contacts, "7916")) == 5
        assert not add_contact(contacts, "", "123", "bad", "")
        assert delete_contact(contacts, "АННА")
        assert not delete_contact(contacts, "Неизвестный")
        assert save_sqlite(contacts, str(Path(folder) / "contacts.db"))
        # connect открывает базу или создаёт её. Контекст with управляет транзакцией:
        # при успехе подтверждает изменения, при исключении откатывает их.
        with sqlite3.connect(str(Path(folder) / "contacts.db")) as connection:
            assert connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 4
        missing = Path(folder) / "new.json"
        assert load_contacts(missing) == [] and missing.exists()
        print("Все проверки пройдены. Тестовые файлы автоматически удалены.")


# main связывает функции в текстовый интерфейс: загрузка, выбор действия, сохранение.
def main():
    # Файлы лежат рядом с программой, независимо от папки запуска.
    folder = Path(__file__).resolve().parent
    filepath = folder / "contacts.json"
    try:
        contacts = load_contacts(filepath)
    except RuntimeError as error:
        print(error)
        return
    # Меню повторяется, пока пользователь не выберет выход и не выполнится break.
    while True:
        print("\n=== Телефонная книга ===\n1. Добавить контакт\n2. Найти контакт"
              "\n3. Удалить контакт\n4. Показать все контакты\n5. Выход"
              "\n6. Показать контакты по группе\n7. Сохранить в SQLite")
        # input возвращает строку, поэтому номера сравниваем с "1", "2" и т. д.
        choice = input("Выберите действие: ").strip()
        # Все четыре поля обязательны. Если проверка не пройдёт, контакт не добавится.
        if choice == "1":
            if add_contact(contacts, input("Имя: "), input("Телефон: "),
                           input("Email: "), input("Группа: ")):
                # Сообщение об успехе выводится только после успешной записи JSON.
                if save_contacts(contacts, filepath):
                    print("Контакт добавлен и сохранён.")
        elif choice == "2":
            list_contacts(find_contact(contacts, input("Имя или телефон: ")))
        elif choice == "3":
            if delete_contact(contacts, input("Полное имя: ")):
                save_contacts(contacts, filepath)
        elif choice == "4":
            list_contacts(contacts)
        # Если сохранить не удалось, продолжаем меню, чтобы можно было повторить попытку.
        elif choice == "5":
            if save_contacts(contacts, filepath):
                print("До свидания!")
                break
        elif choice == "6":
            list_contacts(contacts, input("Группа: "))
        # SQLite сохраняется по выбору пользователя, JSON — после изменений автоматически.
        elif choice == "7":
            save_sqlite(contacts, str(folder / "contacts.db"))
        else:
            print("Выберите номер от 1 до 7.")


# Этот блок запускается при выполнении файла, но не при его импорте как модуля.
if __name__ == "__main__":
    try:
        # Параметр --test включает проверки вместо интерактивного меню.
        if "--test" in sys.argv:
            run_test()
        else:
            main()
    # Ctrl+C или конец ввода завершают программу без длинного сообщения об исключении.
    except (KeyboardInterrupt, EOFError):
        print("\nРабота завершена. Изменения сохраняются после добавления и удаления.")
