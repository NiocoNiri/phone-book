
import json
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path


def validate_contact(name, phone, email, group):
    if not all(isinstance(value, str) for value in (name, phone, email, group)):
        raise ValueError("Все поля контакта должны быть строками.")
    if not name.strip():
        raise ValueError("Имя не должно быть пустым.")
    if not re.fullmatch(r"\+?\d{10,15}", phone.strip()):
        raise ValueError("Телефон: от 10 до 15 цифр, в начале допустим +.")
    if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email.strip()):
        raise ValueError("Введите корректный email, например alice@mail.ru.")
    if not group.strip():
        raise ValueError("Группа не должна быть пустой.")


def add_contact(contacts, name, phone, email, group):
    try:
        validate_contact(name, phone, email, group)
    except ValueError as error:
        print("Ошибка:", error)
        return False
    contacts.append({"name": name.strip(), "phone": phone.strip(),
                     "email": email.strip(), "group": group.strip()})
    return True


def find_contact(contacts, query):
    query = query.strip().casefold()
    return [contact for contact in contacts
            if query in contact["name"].casefold() or query in contact["phone"]]


def delete_contact(contacts, name):
    found = [contact for contact in contacts
             if contact["name"].casefold() == name.strip().casefold()]
    if not found:
        print("Контакт не найден.")
        return False
    contacts[:] = [contact for contact in contacts if contact not in found]
    print("Удалено контактов:", len(found))
    return True


def list_contacts(contacts, group=None):
    selected = contacts if group is None else [
        contact for contact in contacts
        if contact["group"].casefold() == group.strip().casefold()]
    if not selected:
        print("Контакты не найдены.")
    for number, contact in enumerate(selected, 1):
        print(f"{number}. {contact['name']} | {contact['phone']} | "
              f"{contact['email']} | {contact['group']}")


def read_json(filepath):
    with open(filepath, encoding="utf-8") as file:
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


def save_contacts(contacts, filepath="contacts.json"):
    filepath = str(filepath)
    temporary = filepath + ".tmp"
    try:

        if os.path.exists(filepath):
            try:
                read_json(filepath)
            except (ValueError, UnicodeError):
                print("Предупреждение: повреждённый JSON не копируется в .bak.")
            else:
                shutil.copy2(filepath, filepath + ".bak")
        with open(temporary, "w", encoding="utf-8") as file:
            json.dump(contacts, file, ensure_ascii=False, indent=4)
        os.replace(temporary, filepath)

        if not os.path.exists(filepath + ".bak"):
            shutil.copy2(filepath, filepath + ".bak")
        return True
    except (OSError, ValueError, TypeError) as error:
        print("Ошибка сохранения:", error)
        return False
    finally:
        try:
            if os.path.exists(temporary):
                os.remove(temporary)
        except OSError:
            pass


def load_contacts(filepath="contacts.json"):
    filepath = str(filepath)
    try:
        return read_json(filepath)
    except FileNotFoundError:
        print("Файл не найден. Создаётся новая телефонная книга.")
        save_contacts([], filepath)
        return []
    except (ValueError, UnicodeError) as error:
        print("Предупреждение: файл повреждён:", error)
        try:
            contacts = read_json(filepath + ".bak")
            print("Контакты восстановлены из .bak.")
            return contacts
        except (OSError, ValueError, UnicodeError) as backup_error:
            print("Не удалось загрузить резервную копию:", backup_error)

            raise RuntimeError("Восстановите файл или резервную копию.") from backup_error
    except OSError as error:
        raise RuntimeError(f"Не удалось прочитать файл: {error}") from error


def save_sqlite(contacts, filepath="contacts.db"):
    try:
        with sqlite3.connect(filepath) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS contacts (
                name TEXT, phone TEXT, email TEXT, contact_group TEXT)""")
            connection.execute("DELETE FROM contacts")
            connection.executemany("INSERT INTO contacts VALUES (?, ?, ?, ?)",
                                   [(c["name"], c["phone"], c["email"], c["group"])
                                    for c in contacts])
        print("Контакты сохранены в SQLite:", filepath)
        return True
    except (sqlite3.Error, OSError) as error:
        print("Ошибка SQLite:", error)
        return False


def run_test():
    with tempfile.TemporaryDirectory() as folder:
        filepath = Path(folder) / "contacts.json"
        contacts = []
        for number, name in enumerate(["Анна", "Борис", "Вера", "Глеб", "Дарья"]):
            assert add_contact(contacts, name, f"+7916123456{number}",
                               f"contact{number}@mail.ru", "друзья")
        assert save_contacts(contacts, filepath)
        assert load_contacts(filepath) == contacts
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
        with sqlite3.connect(str(Path(folder) / "contacts.db")) as connection:
            assert connection.execute("SELECT COUNT(*) FROM contacts").fetchone()[0] == 4
        missing = Path(folder) / "new.json"
        assert load_contacts(missing) == [] and missing.exists()
        print("Все проверки пройдены. Тестовые файлы автоматически удалены.")


def main():

    folder = Path(__file__).resolve().parent
    filepath = folder / "contacts.json"
    try:
        contacts = load_contacts(filepath)
    except RuntimeError as error:
        print(error)
        return
    while True:
        print("\n=== Телефонная книга ===\n1. Добавить контакт\n2. Найти контакт"
              "\n3. Удалить контакт\n4. Показать все контакты\n5. Выход"
              "\n6. Показать контакты по группе\n7. Сохранить в SQLite")
        choice = input("Выберите действие: ").strip()
        if choice == "1":
            if add_contact(contacts, input("Имя: "), input("Телефон: "),
                           input("Email: "), input("Группа: ")):
                if save_contacts(contacts, filepath):
                    print("Контакт добавлен и сохранён.")
        elif choice == "2":
            list_contacts(find_contact(contacts, input("Имя или телефон: ")))
        elif choice == "3":
            if delete_contact(contacts, input("Полное имя: ")):
                save_contacts(contacts, filepath)
        elif choice == "4":
            list_contacts(contacts)
        elif choice == "5":
            if save_contacts(contacts, filepath):
                print("До свидания!")
                break
        elif choice == "6":
            list_contacts(contacts, input("Группа: "))
        elif choice == "7":
            save_sqlite(contacts, str(folder / "contacts.db"))
        else:
            print("Выберите номер от 1 до 7.")


if __name__ == "__main__":
    try:
        if "--test" in sys.argv:
            run_test()
        else:
            main()
    except (KeyboardInterrupt, EOFError):
        print("\nРабота завершена. Изменения сохраняются после добавления и удаления.")
