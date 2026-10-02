<template>
  <div>
    <h1 class="brand">成员</h1>
    <form @submit.prevent="add">
      <input v-model="name" placeholder="新成员姓名" />
      <button type="submit">添加</button>
    </form>
    <ul class="list">
      <li v-for="m in rows" :key="m.id">
        <strong>{{ m.name }}</strong>
        <span class="muted"> · {{ m.active ? '在岗' : '停用' }} · {{ m.data_quality }}</span>
        <button v-if="m.active && m.data_quality==='clean'"
                class="ghost ban-row-btn" @click="presetMember = m.id">禁配任务…</button>
      </li>
    </ul>
    <BanMatrix :members="rows" :tasks="tasks" :preset-member="presetMember" @changed="load" />
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
import { api } from '../api'
import BanMatrix from '../components/BanMatrix.vue'
const rows = ref([])
const tasks = ref([])
const name = ref('')
const presetMember = ref(null)
async function load() {
  rows.value = await api('/members')
  tasks.value = await api('/tasks')
}
async function add() {
  if (!name.value.trim()) return
  await api('/members', { method: 'POST', body: JSON.stringify({ name: name.value }) })
  name.value = ''; await load()
}
onMounted(load)
</script>
<style scoped>
.ban-row-btn { margin-left: 8px; padding: 3px 10px; font-size: 12px; }
</style>
