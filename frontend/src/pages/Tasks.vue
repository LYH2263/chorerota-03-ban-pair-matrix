<template>
  <div>
    <h1 class="brand">任务</h1>
    <form @submit.prevent="add">
      <input v-model="title" placeholder="任务名" />
      <button type="submit">添加</button>
    </form>
    <ul class="list">
      <li v-for="t in rows" :key="t.id">
        <strong>{{ t.title }}</strong>
        <span class="muted"> · 权重 {{ t.weight }} · {{ t.data_quality }}</span>
        <button class="ghost ban-row-btn" @click="presetTask = t.id">该任务禁配…</button>
      </li>
    </ul>
    <BanMatrix :tasks="rows" :members="members" :preset-task="presetTask" />
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import BanMatrix from '../components/BanMatrix.vue'
const rows = ref([])
const members = ref([])
const title = ref('')
const presetTask = ref(null)
async function load() {
  rows.value = await api('/tasks')
  members.value = await api('/members')
}
async function add() {
  if (!title.value.trim()) return
  await api('/tasks', { method: 'POST', body: JSON.stringify({ title: title.value }) })
  title.value = ''; await load()
}
onMounted(load)
</script>
<style scoped>
.ban-row-btn { margin-left: 8px; padding: 3px 10px; font-size: 12px; }
</style>
