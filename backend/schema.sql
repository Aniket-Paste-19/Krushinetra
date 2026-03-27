DROP TABLE IF EXISTS SearchHistory;
DROP TABLE IF EXISTS DatasetImages;
DROP TABLE IF EXISTS TrainingRuns;
DROP TABLE IF EXISTS Diseases;
DROP TABLE IF EXISTS Plants;
DROP TABLE IF EXISTS Farmers;
DROP TABLE IF EXISTS AdminUsers;

CREATE TABLE AdminUsers (
    AdminID INTEGER PRIMARY KEY AUTOINCREMENT,
    Username TEXT NOT NULL UNIQUE,
    PasswordHash TEXT NOT NULL,
    CreatedDate TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE Farmers (
    FarmerID INTEGER PRIMARY KEY AUTOINCREMENT,
    Name TEXT NOT NULL,
    Email TEXT NOT NULL UNIQUE,
    PasswordHash TEXT NOT NULL,
    Phone TEXT,
    CreatedDate TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    Status TEXT NOT NULL DEFAULT 'active',
    LastLogin TEXT
);

CREATE TABLE Plants (
    PlantID INTEGER PRIMARY KEY AUTOINCREMENT,
    PlantName TEXT NOT NULL UNIQUE,
    Description TEXT
);

CREATE TABLE Diseases (
    DiseaseID INTEGER PRIMARY KEY AUTOINCREMENT,
    PlantID INTEGER NOT NULL,
    DiseaseName TEXT NOT NULL,
    Symptoms TEXT,
    Treatment TEXT,
    Supplement TEXT,
    Notes TEXT,
    FOREIGN KEY (PlantID) REFERENCES Plants(PlantID) ON DELETE CASCADE,
    UNIQUE (PlantID, DiseaseName)
);

CREATE TABLE DatasetImages (
    ImageID INTEGER PRIMARY KEY AUTOINCREMENT,
    PlantID INTEGER NOT NULL,
    DiseaseID INTEGER NOT NULL,
    ImagePath TEXT NOT NULL UNIQUE,
    SourceType TEXT NOT NULL CHECK (SourceType IN ('seed', 'custom')),
    UploadDate TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    IsValidated INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (PlantID) REFERENCES Plants(PlantID) ON DELETE CASCADE,
    FOREIGN KEY (DiseaseID) REFERENCES Diseases(DiseaseID) ON DELETE CASCADE
);

CREATE TABLE SearchHistory (
    SearchID INTEGER PRIMARY KEY AUTOINCREMENT,
    FarmerID INTEGER NOT NULL,
    PlantID INTEGER NOT NULL,
    DiseaseID INTEGER NOT NULL,
    ImagePath TEXT NOT NULL,
    PredictionConfidence REAL NOT NULL,
    ModelVersion TEXT,
    SearchDate TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    SourceType TEXT NOT NULL DEFAULT 'prediction',
    FOREIGN KEY (FarmerID) REFERENCES Farmers(FarmerID) ON DELETE CASCADE,
    FOREIGN KEY (PlantID) REFERENCES Plants(PlantID) ON DELETE CASCADE,
    FOREIGN KEY (DiseaseID) REFERENCES Diseases(DiseaseID) ON DELETE CASCADE
);

CREATE TABLE TrainingRuns (
    TrainingID INTEGER PRIMARY KEY AUTOINCREMENT,
    ModelVersion TEXT NOT NULL,
    DatasetImageCount INTEGER NOT NULL,
    TrainCount INTEGER NOT NULL,
    ValCount INTEGER NOT NULL,
    TestCount INTEGER NOT NULL,
    Accuracy REAL,
    Loss REAL,
    TrainingDate TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ModelPath TEXT NOT NULL,
    Notes TEXT
);

CREATE INDEX idx_farmers_status ON Farmers(Status);
CREATE INDEX idx_search_history_farmer_date ON SearchHistory(FarmerID, SearchDate DESC);
CREATE INDEX idx_dataset_images_source ON DatasetImages(SourceType);
CREATE INDEX idx_training_runs_date ON TrainingRuns(TrainingDate DESC);
