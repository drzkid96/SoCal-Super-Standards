export const agencies = {
  "caltrans": {
    "short": "Caltrans",
    "name": "California Department of Transportation",
    "agency": "State highway design and traffic operations",
    "official": "https://dot.ca.gov/"
  },
  "fhwa": {
    "short": "FHWA",
    "name": "Federal Highway Administration",
    "agency": "Federal traffic control and roadway guidance",
    "official": "https://highways.dot.gov/"
  },
  "ada": {
    "short": "U.S. Access Board",
    "name": "U.S. Access Board",
    "agency": "Federal accessibility guidance",
    "official": "https://www.access-board.gov/"
  },
  "boe": {
    "short": "LA BOE",
    "name": "Los Angeles Bureau of Engineering",
    "agency": "City of Los Angeles · Public Works",
    "official": "https://engineering.lacity.gov/"
  },
  "ladot": {
    "short": "LADOT",
    "name": "Los Angeles Department of Transportation",
    "agency": "City of Los Angeles · Transportation",
    "official": "https://ladot.lacity.gov/"
  }
} as const;

export type AgencyKey = keyof typeof agencies;
