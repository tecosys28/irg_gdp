/**
 * IRG_GDP Master Configuration
 * IPR Owner: Rohit Tidke | Exclusively assigned to: Intech Research Group
 * 
 * COMPLIANCE: No banned words used
 * Banned: digital, exchange, crypto, currency, fungible, non-fungible, 
 *         payment aggregator, voucher, pre-paid, tokenizing, token
 */

const IRG_GDP_CONFIG = {
  // ═══════════════════════════════════════════════════════════════════
  // SYSTEM PARAMETERS
  // ═══════════════════════════════════════════════════════════════════
  
  minting: {
    SALEABLE_PER_GRAM: 9,
    RESERVE_PER_GRAM: 1,
    MAX_MINTING_CAP_GRAMS: 500,
  },
  
  corpusFund: {
    CONTRIBUTION_PERCENT: 20,
    PHYSICAL_GOLD_PERCENT: 5,
    OTHER_INVESTMENTS_PERCENT: 95,
  },
  
  bonusEarmarking: {
    MINTER_SHARE_PERCENT: 6,
    EARMARKING_PERCENTAGE: 11,
  },
  
  lockInPeriods: {
    NEW_JEWELRY_MONTHS: 0,
    OLD_JEWELRY_MONTHS: 12,
    REMADE_JEWELRY_MONTHS: 6,
  },
  
  designerRoyalties: {
    EMERGING_PERCENT: 2,
    ESTABLISHED_PERCENT: 3,
    MASTER_PERCENT: 5,
  },
  
  scfFacilitation: {
    FACILITATION_PERCENT: 7,
  },
  
  goldPurity: {
    '24K': 1.0,
    '22K': 0.9167,
    '18K': 0.75,
    '14K': 0.5833,
  },
  
  // ═══════════════════════════════════════════════════════════════════
  // SUPER CF BANK ACCOUNT
  // ═══════════════════════════════════════════════════════════════════
  
  superCFAccount: {
    accountName: 'Intech Research Group',
    accountNumber: '99620200000108',
    accountType: 'Current Account',
    bankName: 'Bank of Baroda',
    branch: 'Santacruz East',
    city: 'Mumbai',
    postalCode: '400 055',
    country: 'INDIA',
    swiftCode: 'BARB0DBSCRU',
    ifscCode: 'BARB0DBSCRU',
  },
  
  // ═══════════════════════════════════════════════════════════════════
  // BLOCKCHAIN CONFIGURATION
  // ═══════════════════════════════════════════════════════════════════
  
  blockchain: {
    chainId: 888101,
    chainName: 'IRG Chain',
    consensus: 'PBFT+Raft',
    rpcUrl: process.env.BLOCKCHAIN_RPC || 'http://localhost:8545',
    blockTime: 5,
  },
  
  // ═══════════════════════════════════════════════════════════════════
  // LBMA METALS
  // ═══════════════════════════════════════════════════════════════════
  
  lbmaMetals: [
    { id: 'XAU', name: 'Gold', symbol: 'Au' },
    { id: 'XAG', name: 'Silver', symbol: 'Ag' },
    { id: 'XPT', name: 'Platinum', symbol: 'Pt' },
    { id: 'XPD', name: 'Palladium', symbol: 'Pd' },
    { id: 'XRH', name: 'Rhodium', symbol: 'Rh' },
    { id: 'XIR', name: 'Iridium', symbol: 'Ir' },
    { id: 'XRU', name: 'Ruthenium', symbol: 'Ru' },
  ],
  
  // ═══════════════════════════════════════════════════════════════════
  // USER ROLES
  // ═══════════════════════════════════════════════════════════════════
  
  userRoles: {
    JEWELER: { name: 'Jeweler', icon: '💎' },
    HOUSEHOLD: { name: 'Household', icon: '🏠' },
    INVESTOR: { name: 'IRG_GDP Buyer', icon: '📈' },
    RETURNEE: { name: 'Jewelry Returnee', icon: '↩️' },
    DESIGNER: { name: 'Designer', icon: '🎨' },
    OMBUDSMAN: { name: 'Ombudsman', icon: '⚖️' },
    CONSULTANT: { name: 'Consultant', icon: '💼' },
    MARKETMAKER: { name: 'Market Maker', icon: '📊' },
    LICENSEE: { name: 'Licensee', icon: '📋' },
    MINTER: { name: 'FTR Minter', icon: '🪙' },
    TRUSTEE: { name: 'Trustee Banker', icon: '🏦' },
    ADMIN: { name: 'Administrator', icon: '🔧' },
  },
  
  // ═══════════════════════════════════════════════════════════════════
  // FTR CATEGORIES (45+)
  // ═══════════════════════════════════════════════════════════════════
  
  ftrCategories: [
    'Healthcare', 'Education', 'Travel', 'Hospitality', 'Real Estate',
    'Automobile', 'Electronics', 'Fashion', 'Food & Beverage', 'Entertainment',
    'Fitness', 'Insurance', 'Legal Services', 'Financial Services', 'Home Services',
    'Beauty & Wellness', 'Pet Services', 'Photography', 'Event Management', 'Catering',
    'Transportation', 'Logistics', 'IT Services', 'Marketing', 'Consulting',
    'Architecture', 'Interior Design', 'Landscaping', 'Security', 'Cleaning',
    'Laundry', 'Repairs', 'Maintenance', 'Childcare', 'Elder Care',
    'Tutoring', 'Music Lessons', 'Art Classes', 'Sports Training', 'Yoga',
    'Meditation', 'Therapy', 'Diagnostics', 'Pharmacy', 'Dental',
  ],
};

module.exports = IRG_GDP_CONFIG;
