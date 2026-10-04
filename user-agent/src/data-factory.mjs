const companies = {
  prefixes: ['粤海', '南方', '绿源', '启明', '云岭', '江城', '海岚', '锦川', '华晟', '澄远', '森合', '东辰', '远景', '青禾', '新澜'],
  industries: ['新能源', '环境科技', '循环经济', '智能制造', '生态发展', '能源管理', '农业科技', '产业发展'],
  suffixes: ['有限公司', '股份有限公司', '集团有限公司'],
}

const regions = [
  { region: '广东省深圳市', city: '深圳', district: '宝安区' },
  { region: '广东省佛山市', city: '佛山', district: '顺德区' },
  { region: '江苏省苏州市', city: '苏州', district: '工业园区' },
  { region: '浙江省宁波市', city: '宁波', district: '北仑区' },
  { region: '山东省青岛市', city: '青岛', district: '西海岸新区' },
  { region: '四川省成都市', city: '成都', district: '龙泉驿区' },
  { region: '湖北省武汉市', city: '武汉', district: '东西湖区' },
  { region: '广西壮族自治区南宁市', city: '南宁', district: '武鸣区' },
  { region: '云南省昆明市', city: '昆明', district: '晋宁区' },
  { region: '河北省张家口市', city: '张家口', district: '张北县' },
]

const projectTemplates = [
  {
    type: 'renewable_energy', label: '分布式光伏', methodology: 'CM-001-V01', min: 2800, max: 36000,
    describe: (place, scale, tonnes) => `项目位于${place.region}${place.district}，计划在工业厂房屋顶建设约 ${scale} MW 分布式光伏设施，采用高效组件与智能逆变系统。预计每年减少温室气体排放约 ${tonnes} tCO₂e，运营期同步记录发电量、并网电量和设备运行数据。`,
  },
  {
    type: 'renewable_energy', label: '陆上风电', methodology: 'CM-001-V01', min: 18000, max: 120000,
    describe: (place, scale, tonnes) => `项目位于${place.region}${place.district}，拟建设总装机容量约 ${scale} MW 的陆上风电场及配套升压设施。项目通过替代区域电网化石能源电量实现减排，预计年减排 ${tonnes} tCO₂e。`,
  },
  {
    type: 'forestry', label: '生态造林碳汇', methodology: 'AR-CM-001-V01', min: 1500, max: 26000,
    describe: (place, scale, tonnes) => `项目位于${place.region}${place.district}，计划完成约 ${scale} 公顷生态造林与退化林修复，开展苗木成活率、林分蓄积量和扰动情况监测，预计年均净吸收 ${tonnes} tCO₂e。`,
  },
  {
    type: 'energy_efficiency', label: '园区节能改造', methodology: 'CM-002-V01', min: 800, max: 15000,
    describe: (place, scale, tonnes) => `项目覆盖${place.region}${place.district}的生产园区，拟对约 ${scale} 台重点用能设备实施高效电机、余热回收和能源管理系统改造。以历史能耗为基线，预计每年减排 ${tonnes} tCO₂e。`,
  },
  {
    type: 'methane_recovery', label: '甲烷回收利用', methodology: 'CM-077-V01', min: 4000, max: 48000,
    describe: (place, scale, tonnes) => `项目位于${place.region}${place.district}，建设日处理能力约 ${scale} 吨的有机废弃物厌氧处理与甲烷回收系统，回收气体用于发电和供热，预计每年减排 ${tonnes} tCO₂e。`,
  },
]

const behaviorProfiles = [
  { name: '谨慎型', note: '操作前倾向核对页面信息，优先完成必填项。' },
  { name: '效率型', note: '倾向使用最短路径完成任务。' },
  { name: '探索型', note: '会先查看页面信息，再选择下一步操作。' },
]

function hash(value) {
  let state = 2166136261
  for (const character of String(value)) {
    state ^= character.charCodeAt(0)
    state = Math.imul(state, 16777619)
  }
  return state >>> 0
}

function randomFactory(seed) {
  let state = seed >>> 0
  return () => {
    state += 0x6d2b79f5
    let value = state
    value = Math.imul(value ^ (value >>> 15), value | 1)
    value ^= value + Math.imul(value ^ (value >>> 7), value | 61)
    return ((value ^ (value >>> 14)) >>> 0) / 4294967296
  }
}

function pick(random, values) {
  return values[Math.floor(random() * values.length)]
}

function integer(random, min, max) {
  return Math.floor(random() * (max - min + 1)) + min
}

function decimal(random, min, max, digits = 2) {
  const scale = 10 ** digits
  return Math.round((min + random() * (max - min)) * scale) / scale
}

const marketBehaviors = [
  { name: 'resting_sell', label: '卖单挂盘', side: 'sell', fillRatio: 0 },
  { name: 'partial_sell', label: '卖单部分成交', side: 'sell', fillRatio: 0.45 },
  { name: 'filled_sell', label: '卖单完全成交', side: 'sell', fillRatio: 1 },
  { name: 'resting_buy', label: '买单挂盘', side: 'buy', fillRatio: 0 },
  { name: 'partial_buy', label: '买单部分成交', side: 'buy', fillRatio: 0.6 },
]

export function createMarketProfile({ seed, index, issueBase = 320, orderBase = 24, priceBase = 8.5, fixed = false }) {
  const random = randomFactory(hash(`${seed}:market:${index}`))
  if (fixed) {
    const issueQuantity = Number(issueBase)
    const orderQuantity = Math.min(Number(orderBase), issueQuantity)
    return {
      behavior: { name: 'filled_sell', label: '卖单完全成交', side: 'sell' },
      vintageYear: new Date().getFullYear(),
      issueQuantity: String(issueQuantity),
      orderQuantity: String(orderQuantity),
      fillQuantity: String(orderQuantity),
      price: String(Number(priceBase)),
    }
  }

  const behavior = marketBehaviors[index % marketBehaviors.length]
  const issueQuantity = Math.max(20, Math.round(Number(issueBase) * decimal(random, 0.7, 1.4, 3)))
  const desiredOrder = Number(orderBase) * decimal(random, 0.55, 1.65, 3)
  const orderQuantity = Math.max(0.25, Math.min(issueQuantity * 0.35, Math.round(desiredOrder * 4) / 4))
  // The index component keeps visible four-decimal price levels distinct in one order book.
  const price = Math.max(0.01, Math.round((Number(priceBase) * decimal(random, 0.72, 1.48, 6) + index * 0.0013) * 10_000) / 10_000)
  const partialRatio = behavior.fillRatio > 0 && behavior.fillRatio < 1
    ? decimal(random, Math.max(0.2, behavior.fillRatio - 0.16), Math.min(0.82, behavior.fillRatio + 0.16), 3)
    : behavior.fillRatio
  const fillQuantity = partialRatio === 0
    ? 0
    : Math.min(orderQuantity, Math.max(0.25, Math.round(orderQuantity * partialRatio * 4) / 4))
  return {
    behavior: { name: behavior.name, label: behavior.label, side: behavior.side },
    vintageYear: new Date().getFullYear() - integer(random, 0, 5),
    issueQuantity: String(issueQuantity),
    orderQuantity: orderQuantity.toFixed(2).replace(/\.00$/, ''),
    fillQuantity: fillQuantity.toFixed(2).replace(/\.00$/, ''),
    price: price.toFixed(4),
  }
}

export function createIdentity({ batchId, seed, index }) {
  const random = randomFactory(hash(`${seed}:${index}`))
  const serial = String(index + 1).padStart(3, '0')
  const place = pick(random, regions)
  const template = pick(random, projectTemplates)
  const company = `${pick(random, companies.prefixes)}${pick(random, companies.industries)}${pick(random, companies.suffixes)}`
  const phase = pick(random, ['一期', '二期', '示范项目', '改造项目'])
  const estimatedTonnes = integer(random, template.min, template.max)
  const scale = template.type === 'forestry'
    ? integer(random, 120, 3200)
    : template.type === 'methane_recovery'
      ? integer(random, 80, 1200)
      : template.type === 'energy_efficiency'
        ? integer(random, 25, 480)
        : integer(random, 5, 220)
  const projectCode = `CL-${String(batchId).slice(-6)}-${serial}`
  const projectName = `${place.city}${place.district}${template.label}${phase}-${serial}`
  return {
    id: `agent-${serial}`,
    displayName: company,
    email: `carbon.agent+${batchId}.${serial}@example.com`,
    password: 'AgentPassword123!',
    company,
    behavior: pick(random, behaviorProfiles),
    projectName,
    projectCode,
    project: {
      name: projectName,
      projectType: template.type,
      projectTypeLabel: template.label,
      region: place.region,
      methodology: template.methodology,
      estimatedTonnes: String(estimatedTonnes),
      description: template.describe(place, scale, estimatedTonnes),
    },
    documents: {
      projectDesign: `${projectCode}_${template.label}_项目设计文件.pdf`,
      ownership: `${projectCode}_${company}_权属证明.pdf`,
      methodology: `${projectCode}_${template.methodology}_适用性说明.pdf`,
      monitoring: `${projectCode}_监测计划与基线数据.pdf`,
    },
  }
}
