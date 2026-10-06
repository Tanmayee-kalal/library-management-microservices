import os

import pandas as pd
import requests
import streamlit as st


BOOK_URL = os.getenv("BOOK_SERVICE_URL", "http://127.0.0.1:8001")
MEMBER_URL = os.getenv("MEMBER_SERVICE_URL", "http://127.0.0.1:8002")
BORROW_URL = os.getenv("BORROW_SERVICE_URL", "http://127.0.0.1:8003")
NOTIFY_URL = os.getenv(
    "NOTIFICATION_SERVICE_URL",
    "http://127.0.0.1:8004",
)


def api(method, url, **kwargs):
    try:
        response = requests.request(
            method,
            url,
            timeout=5,
            **kwargs,
        )

        if response.ok:
            return response.json(), None

        return None, f"{response.status_code}: {response.text}"

    except requests.RequestException as exc:
        return None, str(exc)


st.set_page_config(
    page_title="Library Management",
    page_icon="📚",
    layout="wide",
)


st.title("📚 Library Management System")

page = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Books",
        "Members",
        "Borrow / Return",
        "Notifications",
    ],
)


if page == "Dashboard":
    st.header("Dashboard")

    status, error = api(
        "GET",
        f"{BORROW_URL}/services/status",
    )

    books, _ = api(
        "GET",
        f"{BOOK_URL}/books",
    )

    members, _ = api(
        "GET",
        f"{MEMBER_URL}/members",
    )

    borrows, _ = api(
        "GET",
        f"{BORROW_URL}/borrows",
    )

    if error:
        st.error(error)
    else:
        st.subheader("Service Health")

        for name, value in status.items():
            if value == "healthy":
                st.success(f"{name}: healthy")
            else:
                st.error(f"{name}: unreachable")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric(
                "Books",
                len(books or []),
            )

        with col2:
            st.metric(
                "Members",
                len(members or []),
            )

        with col3:
            active = sum(
                1
                for borrow in (borrows or [])
                if borrow["returned_at"] is None
            )

            st.metric(
                "Active Borrows",
                active,
            )


elif page == "Books":
    st.header("Books")

    books, error = api(
        "GET",
        f"{BOOK_URL}/books",
    )

    if error:
        st.error(error)
    else:
        st.dataframe(
            pd.DataFrame(books),
            use_container_width=True,
        )

    st.subheader("Add Book")

    with st.form("add_book"):
        title = st.text_input("Title")
        author = st.text_input("Author")
        submitted = st.form_submit_button("Add Book")

        if submitted:
            data, error = api(
                "POST",
                f"{BOOK_URL}/books",
                json={
                    "title": title,
                    "author": author,
                },
            )

            if error:
                st.error(error)
            else:
                st.success("Book added successfully!")


elif page == "Members":
    st.header("Members")

    members, error = api(
        "GET",
        f"{MEMBER_URL}/members",
    )

    if error:
        st.error(error)
    else:
        st.dataframe(
            pd.DataFrame(members),
            use_container_width=True,
        )

    st.subheader("Add Member")

    with st.form("add_member"):
        name = st.text_input("Name")
        email = st.text_input("Email")
        submitted = st.form_submit_button("Add Member")

        if submitted:
            data, error = api(
                "POST",
                f"{MEMBER_URL}/members",
                json={
                    "name": name,
                    "email": email,
                },
            )

            if error:
                st.error(error)
            else:
                st.success("Member added successfully!")


elif page == "Borrow / Return":
    st.header("Borrow / Return")

    members, member_error = api(
        "GET",
        f"{MEMBER_URL}/members",
    )

    books, book_error = api(
        "GET",
        f"{BOOK_URL}/books",
    )

    if member_error:
        st.error(member_error)

    elif book_error:
        st.error(book_error)

    else:
        member_options = {
            f"{member['id']} - {member['name']}": member["id"]
            for member in members
            if member["active"]
        }

        available_books = {
            f"{book['id']} - {book['title']}": book["id"]
            for book in books
            if book["available"]
        }

        st.subheader("Borrow a Book")

        if member_options and available_books:
            selected_member = st.selectbox(
                "Member",
                list(member_options.keys()),
            )

            selected_book = st.selectbox(
                "Book",
                list(available_books.keys()),
            )

            if st.button("Borrow"):
                data, error = api(
                    "POST",
                    f"{BORROW_URL}/borrow",
                    json={
                        "member_id": member_options[selected_member],
                        "book_id": available_books[selected_book],
                    },
                )

                if error:
                    st.error(error)
                else:
                    st.success(
                        f"Borrowed: {data['book']}"
                    )
                    st.info(
                        f"Notification: {data['notification']}"
                    )
        else:
            st.warning(
                "No active members or available books."
            )

    st.subheader("Borrow History")

    borrows, error = api(
        "GET",
        f"{BORROW_URL}/borrows",
    )

    if error:
        st.error(error)
    else:
        st.dataframe(
            pd.DataFrame(borrows),
            use_container_width=True,
        )

        active_borrows = [
            borrow
            for borrow in borrows
            if borrow["returned_at"] is None
        ]

        if active_borrows:
            selected_borrow = st.selectbox(
                "Borrow record to return",
                [
                    f"Borrow #{borrow['id']}"
                    for borrow in active_borrows
                ],
            )

            borrow_id = int(
                selected_borrow.split("#")[1]
            )

            if st.button("Return Book"):
                data, error = api(
                    "POST",
                    f"{BORROW_URL}/return/{borrow_id}",
                )

                if error:
                    st.error(error)
                else:
                    st.success("Book returned successfully!")
                    st.info(
                        f"Notification: {data['notification']}"
                    )


elif page == "Notifications":
    st.header("Notifications")

    notifications, error = api(
        "GET",
        f"{NOTIFY_URL}/notifications",
    )

    if error:
        st.error(error)
    else:
        if notifications:
            st.dataframe(
                pd.DataFrame(notifications),
                use_container_width=True,
            )
        else:
            st.info("No notifications yet.")