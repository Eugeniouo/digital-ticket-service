export function departmentCaption(department) {
  return `Отделение № ${department.code}: ${department.address}`
}

export function departmentOptionLabel(department) {
  return `№ ${department.code} · ${department.address}`
}
