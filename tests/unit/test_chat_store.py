import pytest
from PIL import Image

from lumalock.core.exceptions import UserError
from lumalock.project.chat import ChatStore, ChatTurn, Conversation


def test_chat_asset_paths_and_original_export_protection(photograph, local_storage):
    store = ChatStore()
    original = local_storage / "photo.png"
    Image.fromarray(photograph).save(original)
    name = store.remember_image(original)
    chat = Conversation(originals=[str(original)], selected_image=name, selected_root=name)
    with pytest.raises(UserError, match="original"):
        store.export(chat, name, original)
    with pytest.raises(UserError, match="history"):
        store.export(chat, name, store.asset(name))
    with pytest.raises(UserError, match="reference"):
        store.asset("../../outside.png")


def test_interrupted_chat_recovers_as_retryable(local_storage):
    store = ChatStore()
    chat = Conversation(turns=[ChatTurn(prompt="Edit", source="assets/a.png", root="assets/a.png")])
    store.save(chat)
    restored = store.recent()[0]
    assert restored.turns[0].status == "failed"
    assert "interrupted" in restored.turns[0].error


def test_delete_reclaims_only_unshared_chat_assets_and_preserves_original(
    photograph, local_storage
):
    store = ChatStore()
    source = local_storage / "original.png"
    Image.fromarray(photograph).save(source)
    shared, unique = store.remember_image(source), store.remember_image(source)
    first = Conversation(
        originals=[str(source)],
        selected_image=unique,
        selected_root=shared,
        turns=[
            ChatTurn(prompt="Edit", source=shared, root=shared, result=unique, status="complete")
        ],
    )
    second = Conversation(selected_image=shared, selected_root=shared)
    store.save(first)
    store.save(second)
    assert store.delete(first) == 1
    assert not store.asset(unique).exists()
    assert store.asset(shared).exists()
    assert source.exists()
    assert [chat.id for chat in store.recent()] == [second.id]
    assert store.delete(second) == 1
    assert not store.asset(shared).exists()
    assert source.exists()


def test_delete_preserves_assets_when_other_metadata_cannot_be_read(photograph, local_storage):
    store = ChatStore()
    source = local_storage / "source.png"
    Image.fromarray(photograph).save(source)
    name = store.remember_image(source)
    chat = Conversation(selected_image=name, selected_root=name)
    store.save(chat)
    (store.directory / "broken.json").write_text("invalid JSON")
    assert store.delete(chat) == 0
    assert store.asset(name).exists()


def test_delete_rejects_path_traversal(local_storage):
    store = ChatStore()
    with pytest.raises(UserError, match="identifier"):
        store.delete(Conversation(id="../../outside"))
